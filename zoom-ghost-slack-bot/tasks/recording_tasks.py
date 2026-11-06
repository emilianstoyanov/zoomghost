# tasks/recording_tasks.py
import os
import uuid
import time
import httpx
import logging
import json
from dotenv import load_dotenv
from tasks.celery_worker import celery_app
from utils.slack import send_basic_slack_message

load_dotenv()
logger = logging.getLogger("zoomghost.recording_tasks")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
# AWS API endpoint that processes recordings; always use HTTPS
AWS_ZOOM_WEBHOOK_URL = os.getenv("AWS_ZOOM_WEBHOOK_URL", "").replace("http://", "https://")
if not AWS_ZOOM_WEBHOOK_URL:
    raise RuntimeError("❌ Missing required env var: AWS_ZOOM_WEBHOOK_URL")


def verify_slack_user(user_id: str) -> tuple[bool, str]:
    """
    Check that the user exists and that the bot can reach them.
    
    Returns:
        tuple[bool, str]: (success, error message)
    """
    try:
        logger.info(f"🔍 Checking Slack user {user_id}...")

        # 1. Check whether the user exists
        user_response = httpx.post(
            "https://slack.com/api/users.info",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            data={"user": user_id},
            timeout=10.0
        )
        user_result = user_response.json()

        if not user_result.get("ok"):
            error = user_result.get("error", "unknown_error")
            logger.error(f"❌ Error checking the user: {error}")
            if error == "user_not_found":
                return False, f"❌ No user found with ID {user_id}. Check that the id is correct."
            return False, f"❌ Error accessing the user: {error}"

        user_info = user_result.get("user", {})
        logger.info(f"✅ User found: {user_info.get('name')} (real name: {user_info.get('real_name')})")

        # 2. Check whether we can access the DM channel
        im_response = httpx.post(
            "https://slack.com/api/conversations.open",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"users": [user_id]},
            timeout=10.0
        )
        im_result = im_response.json()

        if not im_result.get("ok"):
            error = im_result.get("error", "unknown_error")
            logger.error(f"❌ Error opening the DM channel: {error}")
            if error == "not_allowed_token_type":
                return False, "❌ The bot does not have the required permissions. Contact an administrator."
            elif error == "cannot_dm_bot":
                return False, "❌ Messages cannot be sent to other bots."
            return False, f"❌ Error opening the DM channel: {error}"

        channel_id = im_result.get("channel", {}).get("id")
        if not channel_id:
            return False, "❌ Could not open a DM channel. Add the bot in Direct Messages."

        logger.info(f"✅ DM channel opened: {channel_id}")
        return True, channel_id

    except Exception as e:
        logger.exception(f"❌ Error checking the Slack user: {str(e)}")
        return False, f"❌ System error while checking the user: {str(e)}"


@celery_app.task(name="tasks.process_recording_from_slack", bind=True)
def process_recording_from_slack(self, recording_url: str, slack_user_id: str):
    """
    Task that sends a Zoom recording to the AWS API for processing.
    
    Args:
        recording_url: URL of the Zoom recording
        slack_user_id: Slack id of the user who requested processing
    """
    try:
        logger.info("=" * 80)
        logger.info(f"🎬 STARTING PROCESSING FOR A NEW RECORDING")
        logger.info(f"📝 Recording URL: {recording_url}")
        logger.info(f"👤 Slack User ID: {slack_user_id}")
        logger.info(f"🌐 AWS Endpoint: {AWS_ZOOM_WEBHOOK_URL}")
        logger.info("=" * 80)

        # 0. Check whether we can access the Slack user
        success, result = verify_slack_user(slack_user_id)
        if not success:
            error_msg = result  # The result is an error message
            logger.error(error_msg)
            return {"status": "error", "error": error_msg, "user_id": slack_user_id}

        channel_id = result  # The result is the DM channel id

        # 1. Notify the user that processing has started
        logger.info(f"📤 Sending the initial message to channel {channel_id}...")
        message_ts = send_basic_slack_message(
            channel_id=channel_id,  # Use the correct channel id
            text=f"🚀 Sending the recording to the processing system...\nThis can take a few minutes, depending on the length."
        )

        if not message_ts:
            logger.warning(f"⚠️ Could not send the initial message to {channel_id}")

        # 2. Prepare the AWS API request in the expected format
        meeting_id = f"slack-{uuid.uuid4()}"  # Generate a unique id for the meeting
        logger.info(f"📝 Generated meeting id: {meeting_id}")

        # Prepare the data in the format the AWS API expects
        aws_payload = {
            "event": "recording.completed",
            "payload": {
                "object": {
                    "id": meeting_id,
                    "host_id": slack_user_id,  # Use the Slack id as host_id
                    "topic": f"Slack-Requested Recording {time.strftime('%Y-%m-%d %H:%M')}",
                    "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "recording_files": [
                        {
                            "download_url": recording_url,
                            "file_type": "MP4",
                            "recording_type": "shared_screen_with_speaker_view"
                        }
                    ]
                }
            }
        }

        logger.info(f"📤 Sending the recording to AWS: {AWS_ZOOM_WEBHOOK_URL}")
        logger.info(f"📦 Payload to AWS:\n{json.dumps(aws_payload, indent=2)}")

        # 3. Send the request to the AWS API with the required headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ZoomGhost-Slack-Bot/1.0",
            "Accept": "application/json",
            "X-Source": "slack-bot",
            "X-Request-ID": str(uuid.uuid4())  # Unique id for each request
        }
        logger.info(f"🔤 Headers to AWS:\n{json.dumps(headers, indent=2)}")

        # Send the request and measure how long it takes
        start_time = time.time()
        response = httpx.post(
            AWS_ZOOM_WEBHOOK_URL,
            json=aws_payload,
            headers=headers,
            timeout=60.0,  # Raise the timeout to 60 seconds
            verify=True  # Verify the SSL certificate
        )
        request_time = time.time() - start_time

        logger.info(f"⏱️ AWS response time: {request_time:.2f} seconds")
        logger.info(f"📥 HTTP Status: {response.status_code}")
        logger.info(f"📥 Response Headers: {dict(response.headers)}")
        logger.info(f"📥 Response Body: {response.text}")

        # 4. Check the response
        if response.status_code in (200, 201, 202):
            logger.info(f"✅ Recording sent to AWS. Response: {response.status_code}")

            success_message = (
                f"✅ The recording was sent for processing!\n"
                f"⏳ The system will process it and you will get an email and a Slack notification when it is ready.\n"
                f"🔗 <{recording_url}|Link to the original recording>\n"
                f"📝 Recording id: {meeting_id}"
            )

            # Update the Slack message only when we have a timestamp
            if message_ts:
                update_slack_message(
                    channel_id=channel_id,
                    message_ts=message_ts,
                    text=success_message
                )
            else:
                # If we have no timestamp, send a new message
                send_basic_slack_message(
                    channel_id=channel_id,
                    text=success_message
                )

            logger.info("=" * 80)
            logger.info("✅ PROCESSING FINISHED SUCCESSFULLY")
            logger.info("=" * 80)

            return {
                "status": "success",
                "aws_response": response.status_code,
                "meeting_id": meeting_id,
                "user_id": slack_user_id,
                "request_time": request_time
            }
        else:
            error_msg = (
                f"❌ Error sending to the AWS API:\n"
                f"Status: {response.status_code}\n"
                f"Headers: {dict(response.headers)}\n"
                f"Body: {response.text}"
            )
            logger.error(error_msg)

            error_message = (
                f"❌ An error occurred while sending the recording:\n"
                f"• HTTP Status: {response.status_code}\n"
                f"• Recording id: {meeting_id}\n"
                f"Please try again later or contact an administrator."
            )

            # Tell the user about the problem only when we have a timestamp
            if message_ts:
                update_slack_message(
                    channel_id=channel_id,
                    message_ts=message_ts,
                    text=error_message
                )
            else:
                # If we have no timestamp, send a new message
                send_basic_slack_message(
                    channel_id=channel_id,
                    text=error_message
                )

            logger.info("=" * 80)
            logger.info("❌ PROCESSING FINISHED WITH AN ERROR")
            logger.info("=" * 80)

            return {
                "status": "error",
                "error": f"AWS API error: {response.status_code}",
                "user_id": slack_user_id,
                "request_time": request_time,
                "meeting_id": meeting_id
            }

    except Exception as e:
        error_msg = f"❌ Error processing the recording: {str(e)}"
        logger.exception(error_msg)

        error_message = (
            f"❌ A system error occurred during processing:\n"
            f"• Error: {str(e)}\n"
            f"• Recording id: {meeting_id if 'meeting_id' in locals() else 'N/A'}\n"
            f"Please try again later or contact an administrator."
        )

        # Tell the user about the problem
        if message_ts:
            update_slack_message(
                channel_id=channel_id,
                message_ts=message_ts,
                text=error_message
            )
        else:
            send_basic_slack_message(
                channel_id=channel_id,
                text=error_message
            )

        logger.info("=" * 80)
        logger.info("❌ PROCESSING ERROR")
        logger.info("=" * 80)

        # On error, still return a result so the failure is visible
        return {
            "status": "error",
            "error": str(e),
            "user_id": slack_user_id,
            "meeting_id": meeting_id if 'meeting_id' in locals() else None
        }


def update_slack_message(channel_id: str, message_ts: str, text: str):
    """Helper that updates a Slack message that was already sent."""
    try:
        if not message_ts or not SLACK_BOT_TOKEN:
            logger.error("❌ Cannot update the message: timestamp or token is missing")
            return False

        response = httpx.post(
            "https://slack.com/api/chat.update",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "channel": channel_id,
                "ts": message_ts,
                "text": text
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
