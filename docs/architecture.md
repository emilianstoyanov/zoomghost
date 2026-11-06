# Architecture

ZoomGhost is three independently deployed applications that share one Supabase project. This document describes the implemented request paths. The diagrams are [diagrams/user-flow.md](diagrams/user-flow.md) and [diagrams/system-architecture.md](diagrams/system-architecture.md).

## Applications

**`zoom-ghost-web`** is a static site. It has no server. The browser loads it from Netlify, then talks to Supabase and to the Heroku API using values from `config.js`.

**`zoom-ghost-slack-bot`** is the orchestration API. A Heroku web dyno runs FastAPI. A worker dyno runs Celery. Both use Redis. This service owns Slack and Zoom OAuth, the Zoom webhook, the Slack button that starts processing, and the recording list API.

**`zoom-bot`** is the processing API. It runs in Docker on ECS Fargate behind an Application Load Balancer. It downloads the recording, calls OpenAI, posts to Slack, and sends email through Amazon SES.

The three codebases do not import each other. The only HTTP link between Heroku and AWS is `AWS_ZOOM_WEBHOOK_URL`.

## Synchronous and asynchronous work

| Step | Mode | Who starts it |
| --- | --- | --- |
| Magic link and session | Synchronous, browser to Supabase | Browser |
| OAuth install and callback | Synchronous HTTP redirects | Browser, then Zoom or Slack |
| `recording.completed` | Heroku returns immediately, then queues Celery | Zoom |
| Slack prompt | Asynchronous Celery task | Heroku worker |
| Process button | Synchronous HTTP from Slack to Heroku, then Heroku waits up to 10 seconds for AWS to accept the job | Slack |
| Transcription and summary | Background task inside the AWS process | AWS, after it has already returned `processing` |
| Slack summary and email | Sequential steps inside that background task | AWS |

Zoom's webhook and Slack's button request are answered by Heroku before the long work finishes. AWS answers Heroku before Whisper and the summary model run.

## Authentication

The site uses Supabase magic links. `supabaseClient.js` creates a client with `detectSessionInUrl`, session persistence, and the storage key `zoom-ghost-auth`. The redirect target is the current browser origin.

After sign-in, the browser reads and writes the `users` row and reads `oauth_tokens` with the anon key. The support widget inserts into `support_messages`.

Zoom and Slack connections start in the browser and finish on Heroku:

1. The site opens `GET /api/slack/install?uid=<user id>` or `GET /api/zoom/install?uid=<user id>`.
2. Heroku puts that id in the OAuth `state` parameter and redirects the browser to Slack or Zoom. It does not check a Supabase session on these routes.
3. Slack or Zoom returns to `/api/slack/oauth/callback` or `/api/zoom/oauth/callback`.
4. Heroku stores the provider user id and tokens in `oauth_tokens` for the user id from `state`, and marks the row active.
5. Heroku redirects the browser to `FRONTEND_URL` with `slack=connected`, `slack=exists`, `slack=error`, `zoom=connected`, or `zoom=error`.

Slack is requested with the scopes `commands`, `chat:write`, `users:read`, and `files:write`. The install routes trust the `uid` query parameter. The recording list is the call that sends the Supabase access token.

`FRONTEND_URL` has no trailing slash. If it is missing when a callback finishes, the redirect raises.

Disconnect in the UI sets `oauth_tokens.is_active` to false. The row stays in the table.

The AWS service does not participate in user OAuth. It uses a Zoom Server-to-Server token, refreshed at startup and every 50 minutes, stored under the id `zoom-global-token-s2s` in `zoom_tokens`.

## Zoom webhook on Heroku

`POST /api/zoom/webhook` accepts Zoom events.

- `endpoint.url_validation` returns the plain token Zoom expects.
- Any event other than `recording.completed` is acknowledged and ignored.
- A missing `host_id`, `meeting_id`, or file list is rejected.
- The preferred download URL is the first MP4. If there is no MP4, the first file is stored.
- Duration below 15 seconds sets `status` to `too_short`. The row is still stored and the Slack prompt is still queued. The 15-second rule is hardcoded.
- The Zoom host must match an active `oauth_tokens` row with `provider=zoom`. If it does not, Heroku returns an error and does not insert the recording.
- A successful insert enqueues the Celery task `handle_zoom_recording`.

Signature check:

- If `ZOOM_WEBHOOK_SECRET_TOKEN` is unset, the check is skipped.
- If the secret is set, Heroku compares `x-zm-signature` with an HMAC-SHA256 prefixed by `v0=`.
- `ZOOM_SKIP_SIGNATURE_CHECK=true` accepts a failed check.

## Slack prompt and the Process button

`handle_zoom_recording` loads the Zoom connection, then the active Slack connection for the same Supabase user. It queues a direct message through `send_slack_message`. The buttons are labeled Process and Ignore. Their action ids stay `process_recording` and `ignore_recording`. The button value for Process is the `zoom_recordings.id`.

The task also builds a payload aimed at AWS. The HTTP call under that payload is commented out, so a new recording does not start AWS by itself.

`POST /api/slack/interactions` handles the click:

- `process_recording` and `process_meeting` load `zoom_recordings` by the button value.
- The handler requires `download_url`, `download_token`, and `recording_files`.
- It appends the download token as `access_token` on the URL and posts one file to `AWS_ZOOM_WEBHOOK_URL`. That file is `recording_files[0]`, which may differ from the MP4 chosen when the row was stored.
- The AWS body uses a new id of the form `slack-<uuid>`, the Slack channel id, and the stored `host_id`.
- Heroku then calls Slack `chat.update` with the bot token.
- `ignore_meeting` updates the message to say the recording was ignored. The button that is actually sent uses `ignore_recording`, so that branch does not run. The click is acknowledged and processing does not start.

`POST /api/slack/webhook` is a second Slack entry point. It answers Events API URL verification and, for a form body whose action id is `process_meeting`, can also post to AWS. The recording prompt from Celery does not target this route. Slack's Interactivity Request URL needs to be `/api/slack/interactions` for the buttons described above.

`tasks.process_recording_from_slack` can post to AWS as well. No HTTP handler calls it. The worker still imports that module, so `AWS_ZOOM_WEBHOOK_URL` must be set or the worker fails at startup.

## AWS processing pipeline

`POST /api/zoom/webhook` on the AWS service schedules `process_zoom_recording` and returns immediately.

Signature check on this service:

- A missing `x-zm-signature` is treated as an internal call and accepted. That is how the Heroku button request is allowed through.
- A missing `ZOOM_WEBHOOK_SECRET_TOKEN` also skips the check.
- When both the header and the secret are present, the signature is HMAC-SHA256 hex of the raw body, without the `v0=` prefix used by Heroku.
- `ZOOM_SKIP_SIGNATURE_CHECK` is injected into the ECS task and is not read by this verifier.

Processing then:

1. Picks a file in order MP4, M4A, MP3. Zoom hosts are downloaded with the Server-to-Server token. A 401 or 403 refreshes the URL and retries. Other URLs are downloaded directly.
2. If the file is larger than 25 MB, splits it into MP3 pieces of at most 600 seconds.
3. Transcribes with OpenAI `whisper-1`.
4. Detects language. Only `bg` and `en` are kept. Anything else becomes `en`.
5. Summarizes with `gpt-3.5-turbo`, splitting the transcript into chunks of at most 4000 characters, with three retries.
6. Posts the summary to Slack when `channel_id` is set. A missing channel skips Slack and continues.
7. If `host_id` is set, looks up an email in Supabase and sends the summary through SES. A missing email skips email.
8. Deletes temporary files.

The SES client is constructed with region `eu-central-1`. The sender address is `SES_SOURCE_EMAIL`. The HTML template footer contains a hardcoded contact address.

`handle_zoom_payload` in the same service can write recording metadata to Supabase and then return without transcribing. The Heroku button path uses `process_zoom_recording`, not that helper.

## Slack settings

`POST /api/slack/settings` opens a Slack modal. Submitting it writes `users.preferences`: notifications, summaries, auto-processing, and minimum duration. The recording webhook and the AWS pipeline do not read those fields. Auto-processing does not skip the Slack prompt. The summaries preference does not turn email on or off.

## Data

Tables used by the running code:

| Table | Used for |
| --- | --- |
| `users` | Profile row and `preferences` |
| `oauth_tokens` | Slack and Zoom connections: provider, provider user id, tokens, `is_active`, metadata |
| `zoom_recordings` | Recording metadata, download URL, token, status |
| `zoom_tokens` | Zoom Server-to-Server token used by AWS |
| `support_messages` | Support form from the website |

`zoom-ghost-slack-bot/infra/sql/SupabaseDatabase.sql` is an older sketch. It includes `meetings` and `notifications` and does not describe the tables above. Treat the code, not that file, as the schema.

## API endpoints

### Heroku (`zoom-ghost-slack-bot`)

| Method and path | Role |
| --- | --- |
| `GET /` | Process check. Returns a short JSON message. |
| `POST /api/slack/hello` | Slack slash-command style hello. |
| `GET /api/slack/install` | Starts Slack OAuth. Requires a `uid` query parameter, used as OAuth `state`. |
| `GET /api/slack/oauth/callback` | Slack OAuth return. Redirects to `FRONTEND_URL`. |
| `POST /api/slack/settings` | Opens the settings modal. |
| `POST /api/slack/interactions` | Modal submission and recording buttons. Process calls AWS. |
| `POST /api/slack/webhook` | Slack Events API verification and an alternate `process_meeting` handler. |
| `GET /api/zoom/install` | Starts Zoom OAuth. Requires a `uid` query parameter, used as OAuth `state`. |
| `GET /api/zoom/oauth/callback` | Zoom OAuth return. Redirects to `FRONTEND_URL`. |
| `POST /api/zoom/webhook` | Zoom URL validation and `recording.completed`. |
| `GET /api/recordings` | Lists recordings for a user. Requires a Bearer token. |

`GET /api/recordings` uses a `user_id` query parameter when one is present, without comparing it to the token. When the query parameter is absent, it asks Supabase Auth who the token belongs to and, if that fails, decodes the JWT with signature verification disabled. `SUPABASE_JWT_SECRET` is required at import and is not used to verify the signature.

### AWS (`zoom-bot`)

| Method and path | Role |
| --- | --- |
| `GET /api/health` | Returns `{"status":"ok"}`. The load balancer uses this path. |
| `GET /api/docs` | FastAPI Swagger UI. |
| `POST /api/summarize` | Returns `Summary of:` plus the first 50 characters. Does not call OpenAI. |
| `POST /api/zoom/webhook` | Accepts the Heroku payload and processes the recording in the background. |
| `POST /api/slack/api/slack/interact` | Slack router mounted under `/api` and `/slack`, with its own `/api/slack` prefix. The recording buttons do not use this path. |

## Celery and Redis

The Celery app is `zoomghost_tasks`. Broker and result backend are both `REDIS_URL`. A `rediss://` URL sets certificate checks to `CERT_NONE`.

Included task modules:

- `tasks.zoom_tasks` — `handle_zoom_recording` (the live prompt) and `zoom.create_meeting` (not called by the HTTP API).
- `tasks.slack_tasks` — `send_slack_message`.
- `tasks.recording_tasks` — `tasks.process_recording_from_slack` (not called by the HTTP API).

`handle_zoom_recording` retries up to three times with backoff. The worker process type in the `Procfile` uses concurrency 2.

There is no periodic schedule. The empty `setup_periodic_tasks` hook does not register jobs.

## Error handling

- Heroku logs the Zoom insert and still attempts to queue Celery. A missing recording id after insert is logged and the HTTP response is still the queued acknowledgement when the exception is caught inside the Celery block.
- A Zoom host with no linked user never reaches Celery.
- A linked user with no active Slack connection ends the Celery task as `no_slack_account`. No prompt is sent and AWS is not called.
- Process fails in Slack if the download URL, token, or file list is missing. The original message is updated with the error.
- AWS logs Slack and email failures and still deletes temporary files. One delivery failing does not by itself fail the other.
- A download failure fails the processing task before transcription.
- OpenAI summary calls retry three times, five seconds apart.

## Security boundaries

- The browser holds the Supabase anon key. Service role keys stay on Heroku and AWS.
- Slack and Zoom install links carry the Supabase user id in the query string and do not require a session. The callback binds the new token to that id.
- Heroku is the only component that should be reachable by Zoom and Slack for product traffic.
- AWS accepts webhook calls that omit `x-zm-signature`. Keep the load balancer URL private to the Heroku app and Zoom, if Zoom is also pointed at it.
- `ZOOM_SKIP_SIGNATURE_CHECK` on Heroku disables a failed signature check. Leave it false outside local development.
- CORS is `CORS_ORIGINS` when set. Otherwise production allows `https://zoomghost.com` and `https://www.zoomghost.com`, and every other `APP_ENV` allows `http://localhost:3000`.
- OAuth returns only to `FRONTEND_URL`.
- Do not commit `.env` or `zoom-ghost-web/config.js`.

## Configuration requirements

The processing path needs, at minimum:

- Frontend `config.js`: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `API_BASE_URL`.
- Heroku: `REDIS_URL`, Supabase service role and JWT secret, Slack and Zoom OAuth clients, `FRONTEND_URL`, `AWS_ZOOM_WEBHOOK_URL`, and a Zoom webhook secret in any shared environment.
- AWS: OpenAI key, Slack bot token, Zoom Server-to-Server credentials, Supabase URL and key, SES sender, and AWS credentials that can send mail in `eu-central-1`.

Names, required versus optional, and examples are in [configuration.md](configuration.md).
