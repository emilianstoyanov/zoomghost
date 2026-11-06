# tasks/slack_tasks.py
import os
import requests
import logging
import httpx
from tasks.celery_worker import celery_app

logger = logging.getLogger("zoomghost.slack")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")


def get_slack_user_id(username: str) -> str | None:
    """
    Converts a username (@username) to a proper Slack user ID (U12345ABC).
    """
    if username and username.startswith("U"):
        return username

    if username.startswith("@"):
        username = username[1:]

    try:
        response = requests.get(
            "https://slack.com/api/users.list",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            timeout=10
        )
        result = response.json()

        if not result.get("ok"):
            logger.error(f"❌ Slack users.list API failed: {result.get('error')}")
            return None

        for member in result.get("members", []):
            if (
                    member.get("name") == username or
                    member.get("real_name") == username or
                    member.get("profile", {}).get("display_name") == username
            ):
                return member.get("id")

        logger.error(f"❌ No user found for username: {username}")
        return None
    except Exception as e:
        logger.exception(f"❌ Error finding Slack user ID: {str(e)}")
        return None


def open_dm_channel(slack_user_id: str) -> str | None:
    """Open a DM channel and return its channel_id when that succeeds."""
    print("➡️  Entering open_dm_channel()")

    if not slack_user_id:
        logger.error("❌ Received an empty slack_user_id")
        print("❌ Received an empty slack_user_id")
        return None

    logger.info(f"🧪 Using SLACK_BOT_TOKEN for user: {slack_user_id}")
    print(f"🧪 SLACK_BOT_TOKEN is being used for: {slack_user_id}")

    # Strip @ when a username was provided
    if slack_user_id.startswith("@"):
        original = slack_user_id
        slack_user_id = slack_user_id[1:]
        logger.warning(f"⚠️ Removed the @ prefix: {original} → {slack_user_id}")
        print(f"⚠️ Removed the @ prefix: {original} → {slack_user_id}")

    # If it does not look like an id (Uxxxx), try to resolve it by username
    if not slack_user_id.startswith("U"):
        print(f"🔍 This looks like a username, looking up an id for: {slack_user_id}")
        resolved_id = get_slack_user_id(slack_user_id)
        if not resolved_id:
            logger.error(f"❌ Could not find a user named: {slack_user_id}")
            print(f"❌ Failed to find an id for username: {slack_user_id}")
            return None
        logger.info(f"🔄 Converted username {slack_user_id} → ID {resolved_id}")
        print(f"✅ Found id: {resolved_id} for username: {slack_user_id}")
        slack_user_id = resolved_id
    else:
        print(f"✅ slack_user_id is already a valid id: {slack_user_id}")

    try:
        logger.info(f"🔄 Trying to open a DM channel for Slack user id: {slack_user_id}")
        print(f"📡 Sending a request to the Slack API to open a DM with id: {slack_user_id}")
        response = httpx.post(
            "https://slack.com/api/conversations.open",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"users": slack_user_id},  # 🟢 Do not pass this as a list
            timeout=10
        )
        result = response.json()
        print(f"📦 Slack API response: {result}")

        if result.get("ok") and result.get("channel"):
            channel_id = result["channel"]["id"]
            logger.info(f"✅ DM channel opened: {channel_id}")
            print(f"✅ DM channel opened: {channel_id}")
            return channel_id

        logger.error(f"❌ Slack DM open failed: {result.get('error')}")
        print(f"❌ Error opening the DM channel: {result.get('error')}")
        return None

    except Exception as e:
        logger.exception(f"❌ Error opening the DM channel: {str(e)}")
        print(f"❌ Exception while opening the channel: {e}")
        return None


@celery_app.task(name="send_slack_message")
def send_slack_message(slack_user_id: str, text: str, blocks: list = None, token: str = None):
    """
    Send a message directly to a Slack user, using a user-level access token.
    """
    try:
        if not token:
            logger.error("❌ No Slack access token was provided (user-level)")
            return None

        if not slack_user_id:
            logger.error("❌ Slack user id was not provided")
            return None

        if not text:
            logger.warning("⚠️ The message text is empty")

        # 🧪 Validate blocks (this matters)
        if blocks:
            for i, action in enumerate(blocks):
                if action.get("type") == "actions":
                    for btn in action.get("elements", []):
                        val = btn.get("value")
                        if not isinstance(val, str):
                            logger.warning(f"⚠️ Converting the button value to str: {btn}")
                            btn["value"] = str(val) if val is not None else ""

        payload = {
            "channel": slack_user_id,
            "text": text
        }

        if blocks:
            payload["blocks"] = blocks

        logger.info(f"📤 Sending a Slack message to {slack_user_id}")
        response = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10.0
        )

        result = response.json()
        if not result.get("ok"):
            logger.error(f"❌ Slack API error while sending: {json.dumps(result, indent=2)}")
            return None

        logger.info(f"✅ Slack message sent to {slack_user_id}")
        return result.get("ts")

    except Exception as e:
        logger.exception(f"❌ Exception while sending the Slack message: {str(e)}")
        return None
