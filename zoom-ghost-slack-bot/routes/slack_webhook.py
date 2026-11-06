# routes/slack_webhook.py
import json
import logging
import httpx
import os
import uuid
import time
from dotenv import load_dotenv
from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse, PlainTextResponse
from tasks.slack_tasks import send_slack_message

router = APIRouter()
load_dotenv()

logger = logging.getLogger("zoomghost.webhook")

# Configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
# AWS API endpoint that processes recordings
AWS_ZOOM_WEBHOOK_URL = os.getenv("AWS_ZOOM_WEBHOOK_URL")
if not AWS_ZOOM_WEBHOOK_URL:
    raise RuntimeError("❌ Missing required env var: AWS_ZOOM_WEBHOOK_URL")


@router.post("/webhook")
async def slack_webhook(request: Request, content_type: str = Header(None)):
    # 👉 URL verification (for the Events API)
    if content_type == "application/json":
        body = await request.json()

        if body.get("type") == "url_verification":
            return JSONResponse(content={"challenge": body["challenge"]})

        # 🎯 Slack event handling (for example reaction, message, and similar events)
        event = body.get("event", {})
        event_type = event.get("type")

        if event_type == "reaction_added":
            logger.info(f"🎉 Reaction added: {event.get('reaction')}")
        elif event_type == "message":
            logger.info(f"💬 New message: {event.get('text')}")

        return {"status": "ok"}

    # 👉 Interactive events from Slack buttons (Block Kit)
    elif content_type == "application/x-www-form-urlencoded":
        form = await request.form()
        payload_str = form.get("payload", "{}")
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON payload: {e}")
            return PlainTextResponse("❌ Invalid payload format")

        if payload.get("type") == "block_actions":
            user = payload.get("user", {})
            user_id = user.get("id")
            actions = payload.get("actions", [])

            if not actions:
                logger.warning("⚠️ Received block_actions with no actions")
                return PlainTextResponse("No actions")

            action = actions[0]
            action_id = action.get("action_id")
            value = action.get("value")  # URL of the recording

            logger.info(f"🔘 Slack interaction from {user_id} - action: {action_id}, value: {value}")

            # Read data from the original message
            original_message = payload.get("message", {})
            original_text = original_message.get("text", "")
            channel_id = payload.get("channel", {}).get("id")
            message_ts = original_message.get("ts")

            # Handle the different button types
            if action_id == "process_meeting":
                # 1. Tell the user that processing has started
                send_slack_message(
                    channel_id=channel_id,
                    thread_ts=message_ts,
                    text="⏳ Sending the recording to the processing system..."
                )

                # 2. Prepare the request to the AWS API
                meeting_id = f"slack-{uuid.uuid4()}"  # Generate a unique id for the meeting

                aws_payload = {
                    "event": "recording.completed",
                    "payload": {
                        "object": {
                            "id": meeting_id,
                            "host_id": user_id,
                            "topic": f"Slack-Requested Recording {time.strftime('%Y-%m-%d %H:%M')}",
                            "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "recording_files": [
                                {
                                    "download_url": value,
                                    "file_type": "MP4"
                                }
                            ],
                            "download_token": ""
                        }
                    }
                }

                # 3. Send the request to the AWS API
                try:
                    logger.info(f"📤 Sending the recording to AWS: {AWS_ZOOM_WEBHOOK_URL}")
                    response = httpx.post(
                        AWS_ZOOM_WEBHOOK_URL,
                        json=aws_payload,
                        timeout=30.0
                    )

                    # 4. Handle the AWS response
                    if response.status_code in (200, 201, 202):
                        logger.info(f"✅ Recording sent to AWS. Response: {response.status_code}")

                        # Tell the user the recording was sent successfully
                        send_slack_message(
                            channel_id=channel_id,
                            thread_ts=message_ts,
                            text=f"✅ The recording was sent for processing!\n⏳ The system will process it and you will get an email and a Slack notification when it is ready."
                        )
                    else:
                        logger.error(f"❌ Error from the AWS API: {response.status_code} - {response.text}")

                        # Tell the user about the error
                        send_slack_message(
                            channel_id=channel_id,
                            thread_ts=message_ts,
                            text=f"❌ An error occurred while sending the recording: HTTP {response.status_code}"
                        )

                except Exception as e:
                    logger.exception(f"❌ Error sending to AWS: {str(e)}")

                    # Tell the user about the error
                    send_slack_message(
                        channel_id=channel_id,
                        thread_ts=message_ts,
                        text=f"❌ An error occurred during processing: {str(e)}"
                    )

                # 5. Update the original message so the buttons are no longer shown
                update_original_message(
                    channel_id=channel_id,
                    message_ts=message_ts,
                    original_text=original_text,
                    status_text="⏳ Processing has started..."
                )

                return JSONResponse(content={"text": "Processing has started"})

            elif action_id == "ignore_meeting":
                # Update the original message to show that the recording was ignored
                update_original_message(
                    channel_id=channel_id,
                    message_ts=message_ts,
                    original_text=original_text,
                    status_text="❌ The recording was ignored."
                )

                return JSONResponse(content={"text": "The recording was ignored"})

    return PlainTextResponse("🤖 Unknown request.")


def update_original_message(channel_id: str, message_ts: str, original_text: str, status_text: str):
    """Update the original message with a new status."""
    try:
        if not SLACK_BOT_TOKEN:
            logger.error("❌ SLACK_BOT_TOKEN is not set")
            return False

        # Build a new block with text and status, and without buttons
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{original_text}\n\n*Status:* {status_text}"
                }
            }
        ]

        response = httpx.post(
            "https://slack.com/api/chat.update",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "channel": channel_id,
                "ts": message_ts,
                "blocks": blocks
            },
            timeout=10.0
        )

        result = response.json()
        if not result.get("ok"):
            logger.error(f"❌ Error updating the message: {result.get('error')}")
            return False

        return True

    except Exception as e:
        logger.exception(f"❌ Error updating the message: {str(e)}")
        return False
