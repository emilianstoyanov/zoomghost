# zoom-bot

AWS processing service for ZoomGhost. It downloads a Zoom cloud recording, transcribes it with OpenAI Whisper, summarizes it with `gpt-3.5-turbo`, posts the summary to Slack, and emails it through Amazon SES.

Heroku calls this service after the user clicks Process in Slack. This service does not call Heroku. Account connection, the Zoom webhook that starts the product flow, and the Slack prompt live in [../zoom-ghost-slack-bot/README.md](../zoom-ghost-slack-bot/README.md). The end-to-end path is in [../docs/architecture.md](../docs/architecture.md).

## What this service does

`POST /api/zoom/webhook` schedules `process_zoom_recording` and returns while the work continues in the background.

1. Choose a file in order MP4, M4A, MP3. Zoom URLs are downloaded with a Server-to-Server token. A 401 or 403 refreshes the URL and retries. Other URLs are downloaded directly.
2. Files larger than 25 MB are split into MP3 segments of at most 600 seconds. ffmpeg does the split.
3. `whisper-1` transcribes the audio.
4. Language detection keeps `bg` or `en`. Other codes become `en`.
5. `gpt-3.5-turbo` summarizes the transcript in chunks of at most 4000 characters, with three retries.
6. Slack delivery runs only when the request includes `channel_id`.
7. Email runs when `host_id` maps to an address in Supabase. The SES client uses region `eu-central-1` and the sender `SES_SOURCE_EMAIL`.
8. Temporary files are removed after delivery.

A Zoom Server-to-Server token is created at startup and refreshed every 50 minutes. It is stored in `zoom_tokens` with id `zoom-global-token-s2s`.

`POST /api/summarize` does not use this pipeline. It returns `Summary of:` plus the first 50 characters of the input.

The container also exposes `POST /api/slack/api/slack/interact`. The Slack buttons in the product call Heroku, not this path.

Requests with no `x-zm-signature` are accepted, which is how the Heroku call gets in. When the header and `ZOOM_WEBHOOK_SECRET_TOKEN` are both present, the body is checked with HMAC-SHA256 hex. This check does not use the `v0=` prefix that Heroku uses. `ZOOM_SKIP_SIGNATURE_CHECK` is not read here.

## HTTP API

| Method and path | Role |
| --- | --- |
| `GET /api/health` | `{"status":"ok"}` |
| `GET /api/docs` | Swagger UI |
| `POST /api/summarize` | Stub summary |
| `POST /api/zoom/webhook` | Start recording processing |
| `POST /api/slack/api/slack/interact` | Extra Slack route, unused by the Heroku buttons |

## Local run

Docker, from this directory:

```bash
docker build -t zoom-bot .
docker run --env-file .env -p 8000:80 zoom-bot
```

The image listens on port 80 and includes ffmpeg. `.env` is not copied into the image.

Without Docker, with ffmpeg on `PATH` and Python 3.10:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

`start_local.sh` runs the same app on port 8001 and will stop other local Uvicorn processes.

| Check | URL |
| --- | --- |
| Docker health | `http://localhost:8000/api/health` |
| `start_local.sh` health | `http://localhost:8001/api/health` |
| Docs | `/api/docs` on that host and port |

Copy `.env.example` to `.env`. The processing path needs `OPENAI_API_KEY`, the Zoom Server-to-Server variables, `SLACK_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`, and SES settings if you want mail. The full list is in [../docs/configuration.md](../docs/configuration.md).

## Layout

```text
app/main.py                 FastAPI app and token refresh on startup
app/router.py               Mounts health, summarize, Zoom, and Slack
app/services/               Download, transcribe, summarize, Slack, Zoom tokens
app/email_service/          SES client and the summary template
Dockerfile                  Python 3.10 image, port 80
.github/workflows/deploy.yml  ECS deploy workflow
infra/                      CloudFormation and task-definition snapshots
```

## Deploy

The GitHub Actions workflow builds this image, pushes it to ECR repository `zoom-bot`, and updates ECS service `zoom-bot-service` on cluster `zoom-bot-cluster` in `eu-central-1`. In this monorepo the workflow file is not at the repository root, so GitHub will not run it until it lives under the root `.github/workflows` directory. Details are in [../docs/deployment.md](../docs/deployment.md) and [infra/README.md](infra/README.md).

The pytest step in the workflow is commented out. `tests/` is present and is not part of the deploy.

## Older descriptions

Earlier notes for this directory described the service joining Zoom meetings as a participant, and listed Lambda, S3, Transcribe, Bedrock, and Step Functions. Those services are not on the path this code runs. The working path is the container, OpenAI, Slack, Supabase, and SES.
