#!/bin/bash

echo "🛑 Checking for running uvicorn process..."

# Try to stop an already running uvicorn (works on Linux and Mac)
if pgrep -f "uvicorn" > /dev/null; then
  echo "🛑 Stopping running uvicorn process..."
  pkill -f "uvicorn"
  sleep 2
else
  echo "✅ No running uvicorn detected."
fi

if ! pip check > /dev/null 2>&1; then
  echo "🔍 Missing or conflicting dependencies detected. Installing..."
  pip install -r requirements.txt
else
  echo "✅ All dependencies are already satisfied."
fi


if [ $? -ne 0 ]; then
  echo "❌ Failed to install requirements. Check your pip and try again."
  exit 1
fi

echo "🚀 Starting Zoom Bot API locally..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001 --log-level debug

