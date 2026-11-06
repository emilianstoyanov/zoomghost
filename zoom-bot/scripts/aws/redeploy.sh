#!/bin/bash
aws ecs update-service \
  --cluster zoom-bot-cluster \
  --service zoom-bot-service \
  --force-new-deployment


# 🔁 Force the container to restart (force new deployment)