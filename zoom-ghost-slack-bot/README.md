# zoom-ghost-slack-bot

Heroku service for ZoomGhost. One web process runs FastAPI. One worker runs Celery against Redis. This service connects Slack and Zoom, receives the Zoom recording webhook, asks the user in Slack, and forwards a chosen recording to the AWS service.

The full request path is in [../docs/architecture.md](../docs/architecture.md). Environment names are in [../docs/configuration.md](../docs/configuration.md).

## Processes

`Procfile`:

```text
web: uvicorn main:app --host=0.0.0.0 --port=${PORT:-5000}
worker: celery -A tasks.celery_worker.celery_app worker --loglevel=info --concurrency=2
```

Celery's broker and backend are `REDIS_URL`. A `rediss://` URL uses `CERT_NONE`. The worker loads `tasks.zoom_tasks`, `tasks.slack_tasks`, and `tasks.recording_tasks`.

`handle_zoom_recording` is the task Zoom events enqueue. It sends the Slack prompt. The HTTP call to AWS inside that task is commented out.

`tasks.process_recording_from_slack` can post to AWS. No route calls it. The module still requires `AWS_ZOOM_WEBHOOK_URL` at import, so the worker will not start without that variable.

`zoom.create_meeting` is defined and is not called by the HTTP API.

## HTTP API

| Method and path | Role |
| --- | --- |
| `GET /` | Process check |
| `POST /api/slack/hello` | Slack hello command |
| `GET /api/slack/install` | Slack OAuth start. Query `uid` becomes OAuth `state`. |
| `GET /api/slack/oauth/callback` | Stores the Slack token and redirects to `FRONTEND_URL` |
| `POST /api/slack/settings` | Opens the preferences modal |
| `POST /api/slack/interactions` | Saves preferences, or handles Process and Ignore |
| `POST /api/slack/webhook` | Events API challenge and an alternate `process_meeting` action |
| `GET /api/zoom/install` | Zoom OAuth start. Query `uid` becomes OAuth `state`. |
| `GET /api/zoom/oauth/callback` | Stores the Zoom token and redirects to `FRONTEND_URL` |
| `POST /api/zoom/webhook` | Zoom URL validation and `recording.completed` |
| `GET /api/recordings` | Recording list for the dashboard |

Slack OAuth requests the scopes `commands`, `chat:write`, `users:read`, and `files:write`.

OAuth redirects use `frontend_redirect`. `FRONTEND_URL` is required at that moment and must not include a trailing slash. Query values are `slack=connected`, `slack=exists`, `slack=error`, `zoom=connected`, and `zoom=error`.

## Zoom recordings

`POST /api/zoom/webhook` stores `recording.completed` in `zoom_recordings` when the Zoom host matches an active Zoom `oauth_tokens` row. The stored download URL prefers the first MP4. Duration under 15 seconds is saved as `too_short` and still queues the Slack prompt.

Signature check uses `ZOOM_WEBHOOK_SECRET_TOKEN` and the `v0=` HMAC prefix. An empty secret skips the check. `ZOOM_SKIP_SIGNATURE_CHECK=true` accepts a bad signature.

## Slack buttons

The prompt buttons are **Process** (`process_recording`) and **Ignore** (`ignore_recording`). The value of Process is the recording row id.

`process_recording` and `process_meeting` load that row, append `access_token` to the download URL, and `POST` one file to `AWS_ZOOM_WEBHOOK_URL`. The file is the first entry in `recording_files`. Heroku waits up to 10 seconds for AWS to accept the request, then updates the Slack message with `chat.update`.

The ignore branch looks for `ignore_meeting`. The button sends `ignore_recording`, so that branch does not run and processing does not start.

Preferences written by the settings modal (`notifications`, `summaries`, `auto_process`, `min_duration`) are stored on `users.preferences`. This service does not read them when a recording arrives.

## Recordings API

`GET /api/recordings` requires a Bearer token. If the `user_id` query parameter is present, that value is used and is not compared with the token. The dashboard always sends `user_id`. Without the query parameter, the handler asks Supabase Auth and then decodes the JWT without verifying the signature.

## CORS

`CORS_ORIGINS` overrides the defaults. When it is unset, `APP_ENV=production` allows `https://zoomghost.com` and `https://www.zoomghost.com`. Any other `APP_ENV` allows `http://localhost:3000`.

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 5000
celery -A tasks.celery_worker.celery_app worker --loglevel=info
```

Redis must already be running. Copy `.env.example` to `.env` first. `GET http://localhost:5000/` returns a short JSON message.

`start_local.py` is gitignored and is not the entry point. Use the commands above.

## Layout

```text
main.py                 FastAPI app, CORS, route mounts
Procfile                web and worker
routes/                 Slack, Zoom, recordings
tasks/                  Celery worker and tasks
utils/                  Slack helpers
scripts/                Local helpers, not used by the dynos
infra/sql/              Older SQL sketch, not the live schema
```

Deploy notes for the two dynos and Redis are in [../docs/deployment.md](../docs/deployment.md).
