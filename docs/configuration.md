# Configuration

Environment and frontend config for all three applications. Example files:

- [zoom-ghost-web/config.example.js](../zoom-ghost-web/config.example.js)
- [zoom-ghost-web/.env.example](../zoom-ghost-web/.env.example)
- [zoom-ghost-slack-bot/.env.example](../zoom-ghost-slack-bot/.env.example)
- [zoom-bot/.env.example](../zoom-bot/.env.example)

Never commit real keys. The examples below are placeholders.

The static site reads `config.js`. It does not read `zoom-ghost-web/.env`. That `.env.example` only mirrors the three values you copy into `config.js`.

## Frontend (`config.js`)

| Variable | Required | Purpose | Example |
| --- | --- | --- | --- |
| `SUPABASE_URL` | Yes | Supabase project URL | `https://YOUR_PROJECT_REF.supabase.co` |
| `SUPABASE_ANON_KEY` | Yes | Public anon key used by the browser | `YOUR_SUPABASE_ANON_KEY` |
| `API_BASE_URL` | Yes | Heroku origin, no path | `https://YOUR_SLACK_BOT_HOST` |

## Heroku API (`zoom-ghost-slack-bot`)

Required to import the web process or the worker, or to finish an OAuth redirect:

| Variable | Required | Purpose | Example |
| --- | --- | --- | --- |
| `REDIS_URL` | Yes for Celery | Broker and result backend. A `rediss://` URL skips certificate verification. | `redis://localhost:6379/0` |
| `SUPABASE_URL` | Yes | Supabase project URL | `https://YOUR_PROJECT_REF.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Server key for `oauth_tokens`, `zoom_recordings`, and `users` | `YOUR_SUPABASE_SERVICE_ROLE_KEY` |
| `SUPABASE_JWT_SECRET` | Yes at import | Loaded by the recordings API. The current decoder does not verify signatures with it. | `YOUR_SUPABASE_JWT_SECRET` |
| `AWS_ZOOM_WEBHOOK_URL` | Yes at import | Where Process posts the recording. | `https://YOUR_ZOOM_BOT_HOST/api/zoom/webhook` |
| `FRONTEND_URL` | Yes when OAuth redirects | Browser destination after Slack or Zoom connect. No trailing slash. | `https://YOUR_FRONTEND_HOST` |
| `SLACK_CLIENT_ID` | Yes for Slack connect | Slack OAuth client | `YOUR_SLACK_CLIENT_ID` |
| `SLACK_CLIENT_SECRET` | Yes for Slack connect | Slack OAuth secret | `YOUR_SLACK_CLIENT_SECRET` |
| `SLACK_REDIRECT_URI` | Yes for Slack connect | Must match the Slack app | `https://YOUR_SLACK_BOT_HOST/api/slack/oauth/callback` |
| `SLACK_BOT_TOKEN` | Yes to message Slack | Bot token used for `chat.update` and task sends | `xoxb-your-bot-token` |
| `ZOOM_CLIENT_ID` | Yes for Zoom connect | Zoom OAuth client | `YOUR_ZOOM_CLIENT_ID` |
| `ZOOM_CLIENT_SECRET` | Yes for Zoom connect | Zoom OAuth secret | `YOUR_ZOOM_CLIENT_SECRET` |
| `ZOOM_REDIRECT_URI` | Yes for Zoom connect | Must match the Zoom app | `https://YOUR_SLACK_BOT_HOST/api/zoom/oauth/callback` |

Optional, or present in the example and unused by this service:

| Variable | Required | Purpose | Example |
| --- | --- | --- | --- |
| `APP_ENV` | No | `production` selects the default CORS origins when `CORS_ORIGINS` is empty. Default `development`. | `development` |
| `DEBUG` | No | Present in the example. Not read by the application modules. | `false` |
| `CORS_ORIGINS` | No | Comma-separated browser origins. Overrides the defaults. | `http://localhost:3000` |
| `ZOOM_WEBHOOK_SECRET_TOKEN` | Recommended | HMAC secret for `x-zm-signature`. If empty, the check is skipped. | `YOUR_ZOOM_WEBHOOK_SECRET` |
| `ZOOM_SKIP_SIGNATURE_CHECK` | No | `true` accepts a failed signature check. | `false` |
| `SLACK_SIGNING_SECRET` | No | Present in the example. The handlers do not verify Slack signatures with it. | `YOUR_SLACK_SIGNING_SECRET` |
| `AWS_ACCESS_KEY_ID` | No | Present in the example. Not read by this service. | `YOUR_AWS_ACCESS_KEY_ID` |
| `AWS_SECRET_ACCESS_KEY` | No | Present in the example. Not read by this service. | `YOUR_AWS_SECRET_ACCESS_KEY` |
| `AWS_REGION` | No | Present in the example. Not read by this service. | `eu-central-1` |
| `SES_SOURCE_EMAIL` | No | Present in the example. Mail is sent by `zoom-bot`. | `noreply@example.com` |

Scripts under `zoom-ghost-slack-bot/scripts/` read extra names. They are not required by the web or worker processes: `SLACK_TEST_USER_ID`, `SLACK_TEST_TOKEN`, `SUPABASE_USER_ID`, `ZOOM_MEETING_ID`, `ZOOM_TEST_DOWNLOAD_URL`, `ZOOM_WEBHOOK_DOWNLOAD_URL`, `ZOOM_WEBHOOK_DOWNLOAD_TOKEN`.

## AWS processing service (`zoom-bot`)

Used by the recording pipeline:

| Variable | Required | Purpose | Example |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes | Whisper and `gpt-3.5-turbo` | `YOUR_OPENAI_API_KEY` |
| `SLACK_BOT_TOKEN` | Yes for Slack delivery | Posts the summary | `xoxb-your-bot-token` |
| `ZOOM_S2S_CLIENT_ID` | Yes for Zoom downloads | Server-to-Server client | `YOUR_ZOOM_S2S_CLIENT_ID` |
| `ZOOM_S2S_CLIENT_SECRET` | Yes for Zoom downloads | Server-to-Server secret | `YOUR_ZOOM_S2S_CLIENT_SECRET` |
| `ZOOM_ACCOUNT_ID` | Yes for Zoom downloads | Zoom account id for the S2S app | `YOUR_ZOOM_ACCOUNT_ID` |
| `SUPABASE_URL` | Yes | Supabase project URL | `https://YOUR_PROJECT_REF.supabase.co` |
| `SUPABASE_KEY` | Yes | Key used by this service. Use a service role key. | `YOUR_SUPABASE_SERVICE_ROLE_KEY` |
| `SES_SOURCE_EMAIL` | Yes for email | From address. Must be an SES identity in `eu-central-1`. | `noreply@example.com` |
| `AWS_ACCESS_KEY_ID` | Yes unless the task role can send mail | SES credentials | `YOUR_AWS_ACCESS_KEY_ID` |
| `AWS_SECRET_ACCESS_KEY` | Yes unless the task role can send mail | SES credentials | `YOUR_AWS_SECRET_ACCESS_KEY` |
| `ZOOM_WEBHOOK_SECRET_TOKEN` | Recommended | Verified only when `x-zm-signature` is also present | `YOUR_ZOOM_WEBHOOK_SECRET` |
| `TEMP_DIR` | No | Working directory for downloads. Default `/tmp`. | `/tmp` |
| `DEBUG` | No | `true` enables extra transcription logging. | `false` |

Present in `.env.example` and injected by the ECS task definition, and not read by the processing path:

| Variable | Purpose |
| --- | --- |
| `ENV` | Example environment label. |
| `ZOOM_CLIENT_ID` | User OAuth client. User OAuth is implemented on Heroku. |
| `ZOOM_CLIENT_SECRET` | User OAuth secret. |
| `ZOOM_REDIRECT_URI` | Example value `https://YOUR_ZOOM_BOT_HOST/api/zoom/oauth/callback`. This service has no Zoom OAuth callback. |
| `ZOOM_SKIP_SIGNATURE_CHECK` | Injected into the task. The AWS verifier does not read it. |
| `SLACK_CLIENT_ID` | Not used by the summary sender. |
| `SLACK_CLIENT_SECRET` | Not used by the summary sender. |
| `SLACK_SIGNING_SECRET` | Not used by the AWS Slack route. |
| `AWS_REGION` | Example `eu-central-1`. The SES client ignores it and uses `eu-central-1`. |

`USER_EMAIL` is read only by `app/email_service/main.py`, a local mail script. `SUPABASE_USER_ID` and `SUPABASE_SERVICE_ROLE_KEY` are read by `get_all_records.py`. The API process uses `SUPABASE_KEY`.

`CI=true` is written by the GitHub Actions dummy `.env` and is consulted by `app/core/secrets.py`.

## ECS secret names

The deploy workflow maps each container variable to a Secrets Manager id:

```text
arn:aws:secretsmanager:eu-central-1:YOUR_AWS_ACCOUNT_ID:secret:zoom-bot/VARIABLE_NAME
```

`VARIABLE_NAME` is the same name as the environment variable, for example `zoom-bot/OPENAI_API_KEY`.
