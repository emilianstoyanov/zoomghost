#!/bin/bash
aws ecs list-tasks \
  --cluster zoom-bot-cluster \
  --service-name zoom-bot-service \
  --output table


# 📋 Show all current tasks


