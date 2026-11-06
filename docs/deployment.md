# Deployment

ZoomGhost is deployed as three separate systems. Nothing in this repository deploys all of them together. Replace every `YOUR_*` placeholder with resources in your own accounts. Do not commit live values.

## Frontend on Netlify

Publish the `zoom-ghost-web` directory as a static site. There is no `netlify.toml` and no build step. `index.html` and `project-details.html` load `config.js` from the same directory.

`config.js` is gitignored. Create it on the deploy from [config.example.js](../zoom-ghost-web/config.example.js):

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `API_BASE_URL` set to the public Heroku origin, with no path

In Supabase Auth, allow the Netlify origin as a redirect URL. On Heroku, set `FRONTEND_URL` to that origin and include it in `CORS_ORIGINS`. If `CORS_ORIGINS` is unset and `APP_ENV=production`, the API allows only `https://zoomghost.com` and `https://www.zoomghost.com`.

## Heroku API and worker

`zoom-ghost-slack-bot/Procfile`:

```text
web: uvicorn main:app --host=0.0.0.0 --port=${PORT:-5000}
worker: celery -A tasks.celery_worker.celery_app worker --loglevel=info --concurrency=2
```

Create a Heroku app from `zoom-ghost-slack-bot`, add a Redis add-on, and set `REDIS_URL` to the add-on URL. Scale both `web` and `worker`. The repository has no `app.json`, `heroku.yml`, or Heroku pipeline config.

Set the variables in [configuration.md](configuration.md) for this application. In particular:

- `AWS_ZOOM_WEBHOOK_URL` is the public AWS webhook, `https://YOUR_ZOOM_BOT_HOST/api/zoom/webhook`.
- `SLACK_REDIRECT_URI` is `https://YOUR_HEROKU_HOST/api/slack/oauth/callback`.
- `ZOOM_REDIRECT_URI` is `https://YOUR_HEROKU_HOST/api/zoom/oauth/callback`.
- `FRONTEND_URL` is the Netlify origin without a trailing slash.
- `ZOOM_WEBHOOK_SECRET_TOKEN` matches the Zoom app. Leave `ZOOM_SKIP_SIGNATURE_CHECK` unset or `false`.

Point the Zoom Event Subscription at `https://YOUR_HEROKU_HOST/api/zoom/webhook`. Point Slack OAuth, Interactivity, and the settings command at the Heroku `/api/slack/...` paths listed in [architecture.md](architecture.md).

`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `SES_SOURCE_EMAIL` appear in the Heroku example file. The Heroku Python service does not read them. Email is sent by `zoom-bot`.

## AWS processing service

The service runs in `eu-central-1` as an ECS Fargate task behind an internet-facing Application Load Balancer.

Checked-in names, from the workflow and the infrastructure snapshot:

| Resource | Name |
| --- | --- |
| ECR repository | `zoom-bot` |
| ECS cluster | `zoom-bot-cluster` |
| ECS service | `zoom-bot-service` |
| Task family | `zoom-bot-task` |
| Container | `zoom-bot` |
| Target group in the snapshot | `zoom-bot-tg-v3` |
| Load balancer in the snapshot | `zoom-bot-alb` |

The container listens on port 80. The target group health check is `GET /api/health` over HTTP. The snapshot listener is HTTP on port 80. The service template uses one task, a public IP, minimum healthy 100 percent, maximum 200 percent, and a deployment circuit breaker with rollback.

The task execution role in the workflow is `ecsTaskExecutionRole`. Account-specific ARNs in the snapshot use `YOUR_AWS_ACCOUNT_ID`, `sg-YOUR_SECURITY_GROUP_ID_1`, `subnet-YOUR_SUBNET_ID_1`, `subnet-YOUR_SUBNET_ID_2`, `subnet-YOUR_SUBNET_ID_3`, and `vpc-YOUR_VPC_ID_1`. The exported task definition is revision 38 of `zoom-bot-task`. That revision is a snapshot. A deploy registers a new revision.

Secrets Manager secret ids used by the workflow have the form `zoom-bot/VARIABLE_NAME` in `eu-central-1`. The SES client in code always uses `eu-central-1`, even if `AWS_REGION` is different. `app/core/secrets_aws.py` defaults to `us-east-1` when `AWS_REGION` is unset. The running container gets its configuration from the task environment, not from that default, as long as the task definition injects the variables.

Verify an SES identity for `SES_SOURCE_EMAIL` in `eu-central-1` before expecting summary mail.

More detail on the snapshot files is in [../zoom-bot/infra/README.md](../zoom-bot/infra/README.md).

## GitHub Actions

The workflow file is [../zoom-bot/.github/workflows/deploy.yml](../zoom-bot/.github/workflows/deploy.yml). It was written when `zoom-bot` was its own repository root.

GitHub Actions runs workflows from `.github/workflows` at the root of the repository. In this monorepo the file is under `zoom-bot/.github/workflows/`, so a push to `main` does not run it. Publishing the monorepo does not move or rewrite that file.

When the workflow does run, on a push to `main` in a repository where it sits at the root, it:

1. Checks out the repository on `ubuntu-latest`.
2. Installs ffmpeg and Python 3.10.
3. Installs `requirements.txt` and pytest.
4. Writes a dummy `.env` for a test step.
5. Skips tests. The "Run tests" step is commented out.
6. Logs in to ECR with `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_ACCOUNT_ID`.
7. Builds `zoom-bot`, tags the git SHA and `latest`, and pushes both.
8. Registers a new `zoom-bot-task` revision whose image is that SHA tag and whose secrets come from Secrets Manager.
9. Updates `zoom-bot-service` on `zoom-bot-cluster` and forces a new deployment.

Region, repository, cluster, service, task family, and container name are the `env` block at the top of the workflow. The Docker build context is the repository root that contains `Dockerfile` and `requirements.txt`.

## What is not deployed from this repo

- Netlify and Heroku have no CI workflow here.
- The CloudFormation snapshot is not applied by GitHub Actions. The workflow updates the ECS service and task definition only.
- Redis is a Heroku add-on, not an AWS resource in this repository.
- Supabase schema changes are not applied by a migration in CI. The SQL file under `zoom-ghost-slack-bot/infra/sql/` does not match the tables the code uses.
