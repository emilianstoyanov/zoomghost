import os
import httpx
import logging

logger = logging.getLogger("zoomghost.slack")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


async def send_slack_interactive_message(channel_id: str, topic: str, recording_id: str) -> dict:
    """
    Send an interactive Slack message with a section and buttons:
    - Process (contains the unique recording_id)
    - Ignore

    Args:
        channel_id: Slack channel or user (user id)
        topic: Meeting topic
        recording_id: Unique Supabase id of the recording

    Returns:
        dict: Slack API JSON response
    """
    if not SLACK_BOT_TOKEN:
        logger.error("❌ SLACK_BOT_TOKEN is not set")
        return {"ok": False, "error": "slack_token_missing"}

    if not channel_id:
        logger.error("❌ Cannot send message: channel_id is empty")
        return {"ok": False, "error": "channel_id_missing"}

    if not recording_id:
        logger.warning("⚠️ Recording ID is missing")

    # Confirm this is a valid channel id or user id
    if not (channel_id.startswith("@") or channel_id.startswith("#") or channel_id.startswith(
            "U") or channel_id.startswith("C")):
        channel_id = f"@{channel_id}"

    try:
        logger.info(f"📨 Sending interactive Slack message to: {channel_id}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "channel": channel_id,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"🎬 We received a recording from the meeting: *{topic}*.\nDo you want to process it?"
                            }
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "✅ Process"
                                    },
                                    "style": "primary",
                                    "value": str(recording_id),  # 🔁 Important: unique id
                                    "action_id": "process_meeting"
                                },
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "❌ Ignore"
                                    },
                                    "style": "danger",
                                    "value": "ignore",
                                    "action_id": "ignore_meeting"
                                }
                            ]
                        }
                    ]
                }
            )

        result = response.json()
        if not result.get("ok"):
            logger.error(f"❌ Slack API error: {result.get('error')}")
        else:
            logger.info(f"✅ Slack interactive message sent to {channel_id}")

        return result

    except Exception as e:
        logger.exception(f"❌ Error sending interactive Slack message: {str(e)}")
        return {"ok": False, "error": str(e)}


async def send_basic_slack_message(channel_id: str, text: str, blocks: list = None) -> str | None:
    """
    Send a plain text message (or one with blocks) to a Slack channel or user.

    Args:
        channel_id: Slack id of a channel or user
        text: Main text
        blocks: Optional list of Block Kit elements

    Returns:
        str | None: Message timestamp (ts), or None on error
    """
    if not SLACK_BOT_TOKEN:
        logger.error("❌ SLACK_BOT_TOKEN is not set!")
        return None

    payload = {
        "channel": channel_id,
        "text": text
    }
    if blocks:
        payload["blocks"] = blocks

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

        result = response.json()
        if not result.get("ok"):
            logger.error(f"❌ Slack API error: {result.get('error')}")
            return None

        logger.info(f"✅ Basic Slack message sent to {channel_id}")
        return result.get("ts")

    except Exception as e:
        logger.exception(f"❌ Error sending the Slack message: {str(e)}")
        return None
