test:
	pytest

format:
	black app

logs:
	aws logs get-log-events \
		--log-group-name /ecs/zoom-bot-task \
		--log-stream-name "$$(aws logs describe-log-streams \
			--log-group-name /ecs/zoom-bot-task \
			--order-by LastEventTime --descending \
			--limit 1 \
			--query 'logStreams[0].logStreamName' --output text)" \
		--limit 100 \
		--query 'events[*].message' --output text \
		--region eu-central-1
