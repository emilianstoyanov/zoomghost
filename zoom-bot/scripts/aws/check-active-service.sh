#!/bin/bash
aws ecs describe-services \
  --cluster zoom-bot-cluster \
  --services zoom-bot-service
