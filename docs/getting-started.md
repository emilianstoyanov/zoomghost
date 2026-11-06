# Getting started

This is how to run the three applications on a development machine. Deployment of the hosted system is in [deployment.md](deployment.md). Variable names are in [configuration.md](configuration.md).

There is no Docker Compose file and no single command that starts the whole system. Run Redis, the Heroku application, its Celery worker, the AWS application, and the static site as separate processes.

## Prerequisites

- Python 3.10 for `zoom-bot`. The Heroku application is a current Python 3 app; its `requirements.txt` does not pin the interpreter.
- pip.
- Redis. The Celery modules read `REDIS_URL` at import. A missing value crashes startup.
- ffmpeg on `PATH` if you run `zoom-bot` outside Docker. The Docker image installs ffmpeg.
- A static file server. Opening `index.html` as a `file://` page will not satisfy the default CORS origin `http://localhost:3000`.
- Optional: Docker, if you want the same image ECS runs.

## Accounts and services

| Service | Why |
| --- | --- |
| Supabase | Auth, `users`, `oauth_tokens`, `zoom_recordings`, `zoom_tokens`, `support_messages` |
| Slack app | OAuth, bot token, interactivity URL, settings command |
| Zoom OAuth app | User connections and the Heroku webhook |
| Zoom Server-to-Server OAuth app | Recording download from `zoom-bot` |
| OpenAI | `whisper-1` and `gpt-3.5-turbo` |
| AWS account with SES | Summary email. Skip only if you do not need email. |
| Redis | Local process, or any Redis URL the worker can reach |

Slack's redirect URL must be the Heroku app's `/api/slack/oauth/callback`. Zoom's redirect URL must be `/api/zoom/oauth/callback`. Zoom's webhook endpoint for the product flow is the Heroku `/api/zoom/webhook`. Slack's Interactivity Request URL is the Heroku `/api/slack/interactions`.

Supabase Auth must allow the site origin as a redirect URL, because the magic link returns to `window.location.origin`.

Add the same origin to `CORS_ORIGINS` when it is not `http://localhost:3000`.

## Environment files

```text
zoom-ghost-web/config.example.js   -> zoom-ghost-web/config.js
zoom-ghost-slack-bot/.env.example  -> zoom-ghost-slack-bot/.env
zoom-bot/.env.example              -> zoom-bot/.env
```

`config.js` and every `.env` are gitignored. The static site does not read `.env`. It reads `window.ZOOMGHOST_CONFIG` from `config.js`.

For local development, point `API_BASE_URL` and `FRONTEND_URL` at the processes below, and set `AWS_ZOOM_WEBHOOK_URL` to the zoom-bot webhook, for example `http://localhost:8000/api/zoom/webhook`. The Heroku code rewrites an `http://` value to `https://` only inside `tasks/recording_tasks.py`. `routes/slack_interactions.py` uses the variable as written, so a local HTTP URL still works for the Process button.

Set `ZOOM_SKIP_SIGNATURE_CHECK=false` unless you are deliberately posting unsigned Zoom bodies to Heroku.

## Frontend

From `zoom-ghost-web`:

```bash
python -m http.server 3000
```

Open `http://localhost:3000`. `index.html` loads `config.js` before `supabaseClient.js`.

Sign-in sends a magic link through Supabase. After the session exists, the Zoom and Slack buttons call `API_BASE_URL` with the Supabase access token.

## Heroku application

From `zoom-ghost-slack-bot`:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 5000
```

The `Procfile` uses the same port when `PORT` is unset. Check `http://localhost:5000/`. The response is a short JSON message.

`start_local.py` in this directory is gitignored and starts a different module path. Use the `uvicorn` command above.

The web process imports the Slack webhook and the recordings API, so these must be set before import: `AWS_ZOOM_WEBHOOK_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_JWT_SECRET`. `REDIS_URL` is required when the worker starts. OAuth callbacks need `FRONTEND_URL` at the moment they redirect.

## Redis and Celery

Start Redis so that `REDIS_URL` resolves. The example value is `redis://localhost:6379/0`.

In a second terminal, from `zoom-ghost-slack-bot`:

```bash
celery -A tasks.celery_worker.celery_app worker --loglevel=info
```

The worker imports `tasks.recording_tasks`, which also requires `AWS_ZOOM_WEBHOOK_URL`. A `rediss://` URL is configured with certificate verification disabled.

The worker is what sends the Slack recording prompt. Without it, Zoom webhooks can still store rows and return `queued`, and the prompt never leaves Redis.

## AWS application

Docker, from `zoom-bot`:

```bash
docker build -t zoom-bot .
docker run --env-file .env -p 8000:80 zoom-bot
```

The image listens on port 80. The mapping above exposes it at `http://localhost:8000`. `.env` is excluded from the image, so pass it with `--env-file` or individual `-e` flags.

Health check: `http://localhost:8000/api/health` returns `{"status":"ok"}`. Interactive docs: `http://localhost:8000/api/docs`.

Without Docker, from `zoom-bot`, with ffmpeg installed:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

`start_local.sh` is a bash helper that installs requirements when `pip check` fails and then runs Uvicorn on port 8001. It also stops other local Uvicorn processes. On Windows, use the explicit `uvicorn` command instead.

On startup the process tries to create a Zoom Server-to-Server token and then refreshes it every 50 minutes. Missing Server-to-Server credentials log an error and the HTTP server still comes up. Downloads fail later.

## How the local processes meet

```text
Browser  ->  http://localhost:3000          static site
Browser  ->  Supabase                       magic link and session
Browser  ->  http://localhost:5000          OAuth and recordings
Zoom     ->  public URL to port 5000       recording.completed
Slack    ->  public URL to port 5000       OAuth and button clicks
Heroku process -> Redis -> Celery worker -> Slack
Process click  -> http://localhost:8000/api/zoom/webhook
zoom-bot -> Zoom, OpenAI, Slack, Supabase, SES
```

Zoom and Slack cannot reach `localhost`. A tunnel, or a deployed Heroku app, has to present `/api/zoom/webhook` and `/api/slack/interactions` on a public HTTPS URL. This repository does not include a tunnel config.

## Health checks

| Service | URL |
| --- | --- |
| Heroku API | `GET http://localhost:5000/` |
| zoom-bot in Docker | `GET http://localhost:8000/api/health` |
| zoom-bot via `start_local.sh` | `GET http://localhost:8001/api/health` |
| zoom-bot API docs | `GET /api/docs` on the same host and port |

## Basic verification

1. `GET /` on port 5000 returns JSON.
2. `GET /api/health` on the zoom-bot port returns `{"status":"ok"}`.
3. The site at port 3000 loads without a missing-`config.js` error in the browser console.
4. Request a magic link to an inbox Supabase can send to, and confirm a session appears.
5. Connect Slack or Zoom and confirm the browser returns to `FRONTEND_URL` with `slack=connected` or `zoom=connected`.
6. With a public webhook URL, finish a Zoom cloud recording and confirm a `zoom_recordings` row and a Slack prompt.
7. Click the process button and confirm zoom-bot logs a download, a Whisper call, and a summary post.

## Known setup limitations

- The three apps must be configured and started separately.
- `zoom-ghost-web/.env` is documentation for humans. The site reads `config.js` only.
- The worker does not call AWS when a recording arrives. Only the Process action does, through `routes/slack_interactions.py`.
- Slack preferences saved by the settings modal are not applied to that flow.
- `POST /api/summarize` does not call OpenAI.
- Tests under `zoom-bot/tests` are not run by the deploy workflow. The pytest step in that workflow is commented out. Collecting those tests can fail on the current `httpx` and Supabase client combination.
- `zoom-ghost-slack-bot/infra/sql/SupabaseDatabase.sql` is not a migration for the tables the code uses.
