# routes/slack_interactions.py
import os
import json
import httpx
import uuid
import time
import logging
from dotenv import load_dotenv
from supabase import create_client
from fastapi import APIRouter, Request
from tasks.celery_worker import celery_app
from fastapi.responses import JSONResponse

router = APIRouter()
load_dotenv()

logger = logging.getLogger("zoomghost.interactions")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# AWS API endpoint that processes recordings
AWS_ZOOM_WEBHOOK_URL = os.getenv("AWS_ZOOM_WEBHOOK_URL")
# Slack configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


def get_slack_user_from_db(user_id: str) -> tuple[bool, str]:
    """
    Find the Slack user in the database.

    Returns:
        tuple[bool, str]: (success, provider_user_id or an error message)
    """
    try:
        # Check whether this user exists in the database
        res = supabase.table("oauth_tokens") \
            .select("provider_user_id") \
            .eq("provider", "slack") \
            .eq("user_id", user_id) \
            .maybe_single() \
            .execute()

        if not res.data:
            logger.error(f"❌ No Slack user found for user_id: {user_id}")
            return False, "❌ We could not find your Slack account. Connect Slack from the web app."

        provider_user_id = res.data.get("provider_user_id")
        if not provider_user_id:
            logger.error(f"❌ Invalid provider_user_id for user_id: {user_id}")
            return False, "❌ Invalid Slack account. Connect Slack again from the web app."

        logger.info(f"✅ Slack user found: {provider_user_id}")
        return True, provider_user_id

    except Exception as e:
        logger.exception(f"❌ Error while searching the database: {str(e)}")
        return False, f"❌ System error while checking the user: {str(e)}"


def get_or_create_dm_channel(user_id: str, slack_user_id: str = None) -> tuple[bool, str]:
    """
    Open or create a DM channel for a user.

    Args:
        user_id: Supabase user id of the user
        slack_user_id: Optional Slack id passed in directly

    Returns:
        tuple[bool, str]: (success, channel_id or an error message)
    """
    try:
        # If a Slack id was not provided, look it up in the database
        if not slack_user_id:
            success, result = get_slack_user_from_db(user_id)
            if not success:
                return False, result
            slack_user_id = result

        # Then open a DM channel
        response = httpx.post(
            "https://slack.com/api/conversations.open",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"users": [slack_user_id]},
            timeout=10.0
        )
        result = response.json()

        if not result.get("ok"):
            error = result.get("error", "unknown_error")
            logger.error(f"❌ Error opening the DM channel: {error}")
            if error == "not_allowed_token_type":
                return False, "❌ The bot does not have the required permissions"
            elif error == "cannot_dm_bot":
                return False, "❌ Messages cannot be sent to other bots"
            elif error == "user_not_found":
                return False, "❌ We could not find the user in Slack"
            elif error == "missing_scope":
                return False, "❌ The bot does not have the required permissions. Ask an administrator to reinstall the bot with the scopes im:write, im:history, and chat:write"
            return False, f"❌ Error opening the DM channel: {error}"

        channel_id = result.get("channel", {}).get("id")
        if not channel_id:
            return False, "❌ Could not open a DM channel"

        logger.info(f"✅ DM channel opened: {channel_id}")
        return True, channel_id

    except Exception as e:
        logger.exception(f"❌ Error opening the DM channel: {str(e)}")
        return False, f"❌ System error: {str(e)}"


@router.post("/interactions")
async def handle_interaction(request: Request):
    form = await request.form()
    payload_str = form.get("payload", "{}")

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON payload: {e}")
        return JSONResponse(content={"text": "❌ Invalid payload format"})

    logger.info(f"📱 Slack interaction received: {payload.get('type', 'unknown')}")

    if payload["type"] == "view_submission":
        logger.info("📝 Handling a submitted Slack modal form")
        user_id = payload["user"]["id"]
        state_values = payload["view"]["state"]["values"]

        try:
            preferences = {
                "notifications": state_values["notifications"]["notifications_select"]["selected_option"]["value"],
                "summaries": state_values["summaries"]["summaries_select"]["selected_option"]["value"],
                "auto_process": state_values["auto_process"]["auto_process_select"]["selected_option"][
                                    "value"] == "true",
                "min_duration": int(state_values["min_duration"]["min_duration_select"]["selected_option"]["value"])
            }
        except Exception as e:
            logger.exception(f"❌ Error reading settings from the form: {str(e)}")
            return {"response_action": "errors", "errors": {"": "❌ Invalid settings in the form."}}

        try:
            res = supabase.table("oauth_tokens") \
                .select("user_id") \
                .eq("provider", "slack") \
                .eq("provider_user_id", user_id) \
                .maybe_single() \
                .execute()

            if not res.data:
                logger.warning(f"⚠️ No user found for Slack ID: {user_id}")
                return {"response_action": "errors", "errors": {"": "User not found."}}

            supabase_user_id = res.data["user_id"]

            supabase.table("users").update({"preferences": preferences}) \
                .eq("id", supabase_user_id) \
                .execute()

            logger.info(f"✅ Settings saved for user: {user_id}")
            return {"response_action": "clear"}

        except Exception as e:
            logger.exception(f"❌ Failed to process the form: {str(e)}")
            return {"response_action": "errors", "errors": {"": "System error. Please try again."}}

    elif payload["type"] == "block_actions":
        user = payload.get("user", {})
        user_id = user.get("id")
        actions = payload.get("actions", [])

        if not actions:
            logger.warning("⚠️ The block_actions payload has no actions")
            return JSONResponse(content={"text": "Invalid action"})

        action = actions[0]
        action_id = action.get("action_id")
        # zoom_meeting_id = action.get("value")
        recording_id = action.get("value")
        message_ts = payload.get("message", {}).get("ts")
        original_text = payload.get("message", {}).get("text", "")

        logger.info(f"🟩 Button clicked: {action_id} for Zoom meeting ID: {recording_id}")

        if action_id in ["process_meeting", "process_recording"]:
            try:
                logger.info(f"🔍 Looking up the recording in Supabase for id: {recording_id}")
                rec_res = supabase.table("zoom_recordings") \
                    .select("*") \
                    .eq("id", recording_id) \
                    .maybe_single() \
                    .execute()

                if not rec_res.data:
                    raise Exception(f"❌ No recording found for Zoom meeting ID: {recording_id}")

                host_id = rec_res.data.get("host_id")
                base_url = rec_res.data.get("download_url")
                download_token = rec_res.data.get("download_token", "")
                recording_files = rec_res.data.get("recording_files", [])

                if not base_url or not download_token:
                    raise Exception("❌ download_url or download_token is missing")

                if not recording_files:
                    raise Exception("❌ recording_files is missing")

                file_type = recording_files[0].get("file_type", "mp4")
                download_url = f"{base_url}?access_token={download_token}"

                logger.info(f"📦 Preparing the AWS request for the Zoom link: {download_url}")

                channel_id = payload.get("channel", {}).get("id")
                aws_payload = {
                    "event": "recording.completed",
                    "channel_id": channel_id,
                    "payload": {
                        "object": {
                            "id": f"slack-{uuid.uuid4()}",
                            "recording_files": [
                                {
                                    "download_url": download_url,
                                    "file_type": file_type.lower()
                                }
                            ],
                            "download_token": "",
                            "host_id": host_id
                        }
                    }
                }

                logger.info(f"Sending aws_payload to AWS with Slack channel_id: {channel_id}")

            except Exception as e:
                logger.exception(f"❌ Error preparing the Zoom link: {str(e)}")
                update_original_message(
                    channel_id=payload.get("channel", {}).get("id"),
                    message_ts=message_ts,
                    original_text=original_text,
                    status_text=f"❌ Failed to start: {str(e)}"
                )
                return JSONResponse(content={"text": f"❌ Failed to send: {str(e)}"})

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    aws_url = AWS_ZOOM_WEBHOOK_URL
                    if not aws_url:
                        raise RuntimeError("Missing required env var: AWS_ZOOM_WEBHOOK_URL")
                    aws_response = await client.post(aws_url, json=aws_payload)

                if aws_response.status_code == 200:
                    status_text = "⏳ Processing has started..."
                    logger.info(f"✅ Payload sent to AWS. Status: 200")
                else:
                    status_text = f"❌ AWS error: {aws_response.text}"
                    logger.error(f"❌ AWS response: {aws_response.text}")

            except Exception as e:
                status_text = f"❌ AWS error: {str(e)}"
                logger.exception(f"❌ Failed to send to AWS")

            update_original_message(
                channel_id=payload.get("channel", {}).get("id"),
                message_ts=message_ts,
                original_text=original_text,
                status_text=status_text
            )
            return JSONResponse(content={"text": status_text})

        elif action_id == "ignore_meeting":
            logger.info(f"🛑 The recording was ignored by user: {user_id}")
            update_original_message(
                channel_id=payload.get("channel", {}).get("id"),
                message_ts=message_ts,
                original_text=original_text,
                status_text="❌ The recording was ignored."
            )
            return JSONResponse(content={"text": "The recording was ignored"})

    logger.warning("⚠️ Unhandled interaction type or missing action.")
    return JSONResponse(content={"text": "✅ Slack interaction received."})


def update_original_message(channel_id: str, message_ts: str, original_text: str, status_text: str):
    """Update the original message with a new status."""
    try:
        if not SLACK_BOT_TOKEN:
            logger.error("❌ SLACK_BOT_TOKEN is not set")
            return False

        # Check that the parameters are valid
        if not channel_id or not message_ts:
            logger.error(f"❌ Invalid parameters for the update: channel_id={channel_id}, message_ts={message_ts}")
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
