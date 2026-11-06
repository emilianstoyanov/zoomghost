#!/bin/bash
aws ecs describe-services \
  --cluster zoom-bot-cluster \
  --services zoom-bot-service \
  --query "services[0].[serviceName,status,desiredCount,runningCount,pendingCount]" \
  --output table



# 🩺 Show the current service status