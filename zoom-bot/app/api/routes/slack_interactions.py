# app/api/routes/slack_interactions.py

from fastapi import APIRouter, Request, BackgroundTasks
from app.services.zoom_service import process_zoom_recording
from app.logging_config import setup_logger

logger = setup_logger(__name__)

router = APIRouter(
    prefix="/api/slack",
    tags=["Slack Interactions"],
)


@router.post("/interact")
async def slack_interact(request: Request, background_tasks: BackgroundTasks):
    payload = await request.form()
    payload_data = payload.get("payload")

    if not payload_data:
        logger.error("❌ No payload received from Slack")
        return {"ok": False}

    import json
    data = json.loads(payload_data)

    action = data.get("actions", [{}])[0]
    action_id = action.get("action_id")
    value = action.get("value")

    logger.info(f"🎛️ Received Slack action: {action_id}, value: {value}")

    if action_id == "process_recording":
        # Read the meeting details from the Slack payload
        meeting_id = data.get("message", {}).get("text", "unknown-meeting-id")
        user_id = data.get("user", {}).get("id")

        # Start processing the recording in the background
        background_tasks.add_task(process_zoom_recording, meeting_id=meeting_id, host_id=user_id, recording_files=[{
            "download_url": value,
            "file_type": "MP4",  # May be MP4, M4A, or MP3; this can be made dynamic later
        }])

        return {"ok": True, "message": "🎬 Recording processing has started!"}

    elif action_id == "ignore_recording":
        logger.info("🚫 User chose to ignore the meeting recording")
        return {"ok": True, "message": "The recording will not be processed."}

    else:
        logger.warning(f"⚠️ Unknown Slack action: {action_id}")
        return {"ok": False, "error": "Unknown action"}
