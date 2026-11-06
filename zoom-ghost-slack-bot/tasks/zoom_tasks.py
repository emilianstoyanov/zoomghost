# tasks/zoom_tasks.py
import httpx
import os
import logging
from supabase import create_client
from tasks.celery_worker import celery_app
from tasks.slack_tasks import send_slack_message

# Configure logger
logger = logging.getLogger("zoomghost.tasks")

# Supabase init
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)


# ✅ Task: create a Zoom meeting
@celery_app.task(name="zoom.create_meeting")
def create_zoom_meeting(user_access_token: str, topic: str, start_time: str):
    zoom_api_url = "https://api.zoom.us/v2/users/me/meetings"

    headers = {
        "Authorization": f"Bearer {user_access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "topic": topic,
        "type": 2,
        "start_time": start_time,
        "duration": 30,
        "timezone": "UTC",
        "settings": {
            "join_before_host": True,
            "approval_type": 0
        }
    }

    try:
        response = httpx.post(zoom_api_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"❌ Failed to create Zoom meeting: {str(e)}")
        return {"error": "Failed to create Zoom meeting", "details": str(e)}


@celery_app.task(
    name="handle_zoom_recording",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def handle_zoom_recording(self, data):
    try:
        topic = data.get("topic", "Untitled Meeting")
        logger.info(f"🔄 [handle_zoom_recording] Start processing topic: {topic}")

        host_id = data.get("host_id")
        if not host_id:
            raise ValueError("Missing host_id")

        # 🔍 Find the Supabase user_id from the Zoom host_id
        user_resp = supabase.table("oauth_tokens") \
            .select("user_id") \
            .eq("provider", "zoom") \
            .eq("provider_user_id", host_id) \
            .eq("is_active", True) \
            .maybe_single().execute()

        if not user_resp.data:
            logger.warning(f"⚠️ No Supabase user found for Zoom host_id: {host_id}")
            return {"status": "no_user_found"}

        user_id = user_resp.data.get("user_id")
        if not user_id:
            return {"status": "missing_user_id"}

        # 🔍 Load the Slack user id and token
        slack_resp = supabase.table("oauth_tokens") \
            .select("provider_user_id, access_token") \
            .eq("provider", "slack") \
            .eq("user_id", user_id) \
            .eq("is_active", True) \
            .maybe_single().execute()

        if not slack_resp.data:
            logger.warning(f"⚠️ No Slack account found for user_id: {user_id}")
            return {"status": "no_slack_account"}

        slack_user_id = slack_resp.data.get("provider_user_id")
        slack_token = slack_resp.data.get("access_token")

        if not slack_user_id or not slack_token:
            return {"status": "missing_slack_credentials"}

        recording_id = data.get("id")
        if not recording_id:
            logger.error("❌ Missing recording ID from Supabase")
            return {"status": "missing_recording_id"}

        logger.info(f"🎯 Preparing Slack button with recording ID: {recording_id}")

        message = (
            f"🎥 New Zoom recording: *{topic}*\n"
            f"📅 Started: {data.get('start_time', 'Unknown')}\n"
            f"💾 Ready to process. Do you want to process it?"
        )

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Process"},
                        "style": "primary",
                        "value": str(recording_id),
                        "action_id": "process_recording"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Ignore"},
                        "style": "danger",
                        "value": "ignore",
                        "action_id": "ignore_recording"
                    }
                ]
            }
        ]

        # 🚀 Send the message
        send_slack_message.delay(
            slack_user_id=slack_user_id,
            text=message,
            blocks=blocks,
            token=slack_token
        )

        logger.info(f"📨 Slack message queued for {slack_user_id}")

        # 👇 Added: pass the required data back to AWS (when needed)
        aws_payload = {
            "event": "recording.completed",
            "channel_id": slack_user_id,  # DM channel fallback (when it is used)
            "user_id": user_id,
            "slack_user_id": slack_user_id,
            "payload": {
                "object": {
                    "id": recording_id,
                    "host_id": host_id,
                    "topic": topic,
                    "start_time": data.get("start_time"),
                    "recording_files": data.get("recording_files", [])
                }
            }
        }

        # Example of sending to AWS (if this function should do it):
        # async def post_to_aws():
        #     async with httpx.AsyncClient() as client:
        #         await client.post("https://your-aws-url/api/zoom/webhook", json=aws_payload)

        return {
            "status": "queued",
            "channel": slack_user_id,
            "topic": topic,
            "user_id": user_id,
            "slack_user_id": slack_user_id
        }

    except Exception as e:
        logger.exception(f"❌ Exception in handle_zoom_recording: {str(e)}")
        raise self.retry(exc=e, countdown=10)
