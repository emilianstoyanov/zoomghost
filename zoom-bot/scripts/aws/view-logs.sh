#!/bin/bash

# 📁 Exact CloudWatch log group name (may be /ecs/zoom-bot-task)
LOG_GROUP_NAME="/ecs/zoom-bot-task"

# 🔍 Take the latest available log stream
LOG_STREAM_NAME=$(aws logs describe-log-streams \
  --log-group-name "$LOG_GROUP_NAME" \
  --order-by LastEventTime \
  --descending \
  --limit 1 \
  --query 'logStreams[0].logStreamName' \
  --output text 2>/dev/null)

# ❌ If there is no log stream yet (no logs have been written)
if [[ -z "$LOG_STREAM_NAME" || "$LOG_STREAM_NAME" == "None" ]]; then
  echo "⚠️  No logs available for $LOG_GROUP_NAME"
  echo "ℹ️  Check that the task is running and has written logs."
  exit 1
fi

echo "📄 Latest logs from: $LOG_STREAM_NAME"
echo "-------------------------------------------"

# 🧾 Print the last 30 log messages
aws logs get-log-events \
  --log-group-name "$LOG_GROUP_NAME" \
  --log-stream-name "$LOG_STREAM_NAME" \
  --limit 30 \
  --query 'events[*].message' \
  --output text
