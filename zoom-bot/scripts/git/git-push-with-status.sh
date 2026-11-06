#!/bin/bash

BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "🚀 Pushing to GitHub for branch: $BRANCH"
git push "$@"

# Only on main: watch the GitHub Action
if [[ "$BRANCH" != "main" ]]; then
  exit 0
fi

echo "⏳ Waiting for the GitHub Action to start..."
sleep 5

# Take the latest active (or new) run
RUN_ID=$(gh run list --limit 1 --branch "$BRANCH" --json databaseId,status --jq 'map(select(.status != "completed")) | .[0].databaseId' 2>/dev/null)

# If none is found, wait another 5 seconds
if [[ -z "$RUN_ID" ]]; then
  echo "⏳ It has not started yet... waiting another 10 seconds..."
  sleep 10
  RUN_ID=$(gh run list --limit 1 --branch "$BRANCH" --json databaseId,status --jq 'map(select(.status != "completed")) | .[0].databaseId' 2>/dev/null)
fi

if [[ -z "$RUN_ID" ]]; then
  echo "❌ Could not find an active GitHub Action run for '$BRANCH'."
  exit 1
fi

echo "🔍 Watching run status: $RUN_ID"
gh run watch "$RUN_ID" --exit-status
EXIT_CODE=$?

# Get the link to the run
RUN_URL=$(gh run view "$RUN_ID" --json url --jq '.url')

if [[ $EXIT_CODE -eq 0 ]]; then
  echo "✅ Action succeeded! 🔗 $RUN_URL"
else
  echo "❌ Action failed! 🔗 $RUN_URL"

  echo ""
  echo "🧾 Latest logs from the failed steps:"
  gh run view "$RUN_ID" --log-failed --exit-status || echo "⚠️ No logs are available, or the CLI could not retrieve them."
fi
