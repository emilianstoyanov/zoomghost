#!/bin/bash

CLUSTER_NAME="zoom-bot-cluster"
SERVICE_NAME="zoom-bot-service"

# Stop the bot
echo "Stopping bot..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --desired-count 0

# Wait until the shutdown settles
echo "Waiting for service to stabilize after stop..."
aws ecs wait services-stable \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME

# Start the bot
echo "Starting bot..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --desired-count 1

# Wait until startup settles
echo "Waiting for service to stabilize after start..."
aws ecs wait services-stable \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME

echo "✅ Bot restart completed."
