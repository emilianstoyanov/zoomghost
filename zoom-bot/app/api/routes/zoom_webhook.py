# app/api/routes/zoom_webhook.py
import os
import hmac
import json
import hashlib

from datetime import datetime
from dotenv import load_dotenv
from fastapi import Header, APIRouter, Request, BackgroundTasks, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from app.logging_config import setup_logger
from app.services.zoom_service import process_zoom_recording

router = APIRouter()
logger = setup_logger(__name__)
load_dotenv()

ZOOM_WEBHOOK_SECRET_TOKEN = os.getenv("ZOOM_WEBHOOK_SECRET_TOKEN")


class RecordingFile(BaseModel):
    download_url: str
    file_type: str
    recording_type: Optional[str] = None


class Recording(BaseModel):
    id: str
    host_id: str
    topic: str
    start_time: datetime
    recording_files: List[RecordingFile]


class ZoomWebhookPayload(BaseModel):
    event: Optional[str] = None
    payload: Optional[dict] = None
    download_url: Optional[str] = None
    file_type: Optional[str] = None
    topic: Optional[str] = None
    meeting_id: Optional[str] = None
    host_id: Optional[str] = None
    start_time: Optional[datetime] = None
    channel_id: Optional[str] = None


@router.post("/webhook", tags=["Zoom Webhooks"])
async def handle_zoom_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        x_zm_signature: Optional[str] = Header(None)
):
    try:
        raw_body = await request.body()

        # 🔐 Verify the Zoom signature
        if not verify_zoom_signature(raw_body, x_zm_signature):
            logger.warning("🚫 Request rejected: invalid signature.")
            raise HTTPException(status_code=403, detail="Invalid Zoom signature.")

        data = json.loads(raw_body)
        logger.info(f"📥 New request received at /api/zoom/webhook: {json.dumps(data)[:500]}...")

        # 🎯 Zoom Webhook
        if data.get("event") and data.get("payload"):
            event_type = data.get("event")
            logger.info(f"📌 Zoom Event: {event_type}")

            if event_type != "recording.completed":
                logger.warning(f"⚠️ Ignored unknown event type: {event_type}")
                return {"status": "ignored", "event": event_type}

            payload = data["payload"]["object"]
            meeting_id = str(payload.get("id", "unknown"))
            topic = payload.get("topic", "Untitled Meeting")
            host_id = payload.get("host_id", "unknown")
            start_time = payload.get("start_time", datetime.utcnow().isoformat())
            recording_files = payload.get("recording_files", [])

            if not recording_files:
                logger.error("❌ The Zoom webhook payload has no recording files.")
                raise HTTPException(status_code=400, detail="No recording files found.")

            logger.info(f"✅ Processing Zoom recording: {topic} ({meeting_id})")

            background_tasks.add_task(
                process_zoom_recording,
                meeting_id=meeting_id,
                host_id=host_id,
                topic=topic,
                start_time=start_time,
                recording_files=recording_files
            )

            return {"status": "processing", "meeting_id": meeting_id, "topic": topic}

        # 🎯 Manual request (from Slack)
        elif data.get("download_url") and data.get("meeting_id"):
            download_url = data["download_url"]
            file_type = data.get("file_type", "M4A")
            topic = data.get("topic", "Untitled Meeting")
            meeting_id = data["meeting_id"]
            host_id = data.get("host_id", "unknown")
            start_time = data.get("start_time", datetime.utcnow().isoformat())
            channel_id = (
                    data.get("channel_id") or
                    data.get("payload", {}).get("channel_id") or
                    data.get("payload", {}).get("object", {}).get("channel_id")
            )

            logger.info(f"✅ Processing Slack recording: {topic} ({meeting_id}) | Channel ID: {channel_id}")

            if not channel_id:
                logger.warning("⚠️ channel_id was not provided – the Slack message may not be delivered.")

            background_tasks.add_task(
                process_zoom_recording,
                meeting_id=meeting_id,
                host_id=host_id,
                topic=topic,
                start_time=start_time,
                recording_files=[{
                    "download_url": download_url,
                    "file_type": file_type,
                    "recording_type": None
                }],
                channel_id=channel_id
            )

            return {"status": "processing", "meeting_id": meeting_id, "topic": topic}

        else:
            logger.error("❌ Invalid request format (required fields are missing).")
            raise HTTPException(status_code=400, detail="Invalid webhook payload format.")

    except Exception as e:
        logger.exception(f"❌ Failed to process the request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")


def verify_zoom_signature(request_body: bytes, signature: Optional[str]) -> bool:
    if not signature:
        logger.info("ℹ️ x-zm-signature is missing — treating this as an internal request (Slack). Skipping verification.")
        return True

    if not ZOOM_WEBHOOK_SECRET_TOKEN:
        logger.warning("⚠️ ZOOM_WEBHOOK_SECRET_TOKEN is not set — skipping verification.")
        return True

    try:
        expected_signature = hmac.new(
            key=ZOOM_WEBHOOK_SECRET_TOKEN.encode(),
            msg=request_body,
            digestmod=hashlib.sha256
        ).hexdigest()
        valid = hmac.compare_digest(expected_signature, signature)
        if not valid:
            logger.error("❌ Invalid Zoom webhook signature!")
        return valid
    except Exception as e:
        logger.exception(f"❌ Error while verifying the Zoom signature: {str(e)}")
        return False
