#!/bin/bash
aws ecs update-service \
  --cluster zoom-bot-cluster \
  --service zoom-bot-service \
  --desired-count 0
