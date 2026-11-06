# zoom-bot infrastructure

Snapshot of the AWS resources that serve the processing API, plus the GitHub Actions workflow that updates the ECS service. Runtime behavior of the container is in [../README.md](../README.md). How this fits Netlify, Heroku, and Supabase is in [../../docs/deployment.md](../../docs/deployment.md).

The files in this directory are templates. Account ids, security groups, subnets, and the load balancer listener use `YOUR_*` placeholders. Fill them in for your own account before applying a template. Do not commit real identifiers.

## Files

| File | Contents |
| --- | --- |
| `ecs-zoom-bot-service-stack.json` | CloudFormation snapshot for the ECS service, target group, and listener rule |
| `zoom-bot-task-definition.json` | Exported task definition. Secrets are names, not values. |

The task definition snapshot is family `zoom-bot-task`, revision 38. A GitHub Actions deploy registers a new revision. Revision 38 is the exported copy, not a promise of what is currently running.

## Resources in the snapshot

| Piece | Value |
| --- | --- |
| ECS service | `zoom-bot-service` |
| Cluster | `zoom-bot-cluster` |
| Launch type | Fargate |
| Desired count | 1 |
| Platform version | `LATEST` |
| Public IP | Enabled |
| Deployment | Minimum healthy 100%, maximum 200%, circuit breaker with rollback |
| Load balancer | `zoom-bot-alb`, internet-facing |
| Listener | HTTP port 80 |
| Target group | `zoom-bot-tg-v3`, target type `ip`, port 80, HTTP |
| Health check | `GET /api/health` |
| Deregistration delay | 300 seconds |
| Region used by the workflow and SES | `eu-central-1` |

Security group, VPC, and subnet fields in the template are placeholders: `sg-YOUR_SECURITY_GROUP_ID_1`, `vpc-YOUR_VPC_ID_1`, `subnet-YOUR_SUBNET_ID_1`, `subnet-YOUR_SUBNET_ID_2`, `subnet-YOUR_SUBNET_ID_3`. The listener ARN uses `YOUR_AWS_ACCOUNT_ID`, `YOUR_LOAD_BALANCER_NAME`, and `YOUR_LISTENER_ID`.

The template does not create the VPC, subnets, security group, cluster, or the task definition. Those have to exist before the stack is applied. The health check must return HTTP 200 from `/api/health`.

CloudFormation outputs in the template are `ClusterName`, `ECSService`, `TargetGroup`, and `ListenerRule`.

## Secrets

The task definition and the deploy workflow read Secrets Manager entries:

```text
arn:aws:secretsmanager:eu-central-1:YOUR_AWS_ACCOUNT_ID:secret:zoom-bot/VARIABLE_NAME
```

The container receives `OPENAI_API_KEY`, `SLACK_BOT_TOKEN`, `SES_SOURCE_EMAIL`, Zoom Server-to-Server credentials, `SUPABASE_URL`, `SUPABASE_KEY`, and the other names listed in [../../docs/configuration.md](../../docs/configuration.md). The SES client in the application always uses `eu-central-1`.

## Applying the snapshot

1. Open CloudFormation and create a stack.
2. Upload `ecs-zoom-bot-service-stack.json`.
3. Replace the placeholders with resources in your account.
4. Register a task definition separately, or let the GitHub Actions workflow register one.

To refresh the local task-definition file from a live account:

```bash
aws ecs describe-task-definition \
  --task-definition zoom-bot-task \
  --query "taskDefinition" \
  --output json > infra/zoom-bot-task-definition.json
```

Review the file before committing it. Remove account-specific ids and confirm it contains secret names only.

## GitHub Actions

The workflow is [../.github/workflows/deploy.yml](../.github/workflows/deploy.yml). It checks out the repo, installs Python 3.10 and ffmpeg, builds the Docker image, pushes `zoom-bot` to ECR, registers a new task revision, and forces a new deployment of `zoom-bot-service`.

The test step in that workflow is commented out. The workflow also expects to live at the root of the Git repository that GitHub Actions runs. In this monorepo it is under `zoom-bot/.github/workflows/`, so a push to the monorepo `main` branch does not start it. See [../../docs/deployment.md](../../docs/deployment.md).
