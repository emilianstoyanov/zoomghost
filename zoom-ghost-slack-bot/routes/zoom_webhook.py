# routes/zoom_webhook.py
import json
import os, hmac, hashlib, logging
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from supabase import create_client
from tasks.zoom_tasks import handle_zoom_recording  # ✨ Celery task

# 🔧 Initialization
router = APIRouter()
logger = logging.getLogger("zoomghost.webhook")

load_dotenv()
ZOOM_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


@router.post("/webhook")
async def zoom_webhook(request: Request):
    logger.info("🌐 ➡️ POST /webhook - request received from Zoom")

    body = await request.body()
    try:
        event_data = await request.json()
    except Exception as e:
        logger.error(f"❌ JSON decode error: {e}")
        return {"status": "invalid json"}

    event_type = event_data.get("event", "unknown")
    logger.info(f"📥 Zoom event received: {event_type}")

    # ✅ Signature verification
    if ZOOM_SECRET:
        zm_signature = request.headers.get("x-zm-signature", "")
        computed_signature = f"v0={hmac.new(ZOOM_SECRET.encode(), body, hashlib.sha256).hexdigest()}"
        logger.debug(f"🔒 Zoom signature header: {zm_signature}")
        logger.debug(f"🔐 Computed signature: {computed_signature}")

        if not zm_signature or not hmac.compare_digest(computed_signature, zm_signature):
            if os.getenv("ZOOM_SKIP_SIGNATURE_CHECK", "").lower() != "true":
                logger.warning("⚠️ Signature check failed. Rejecting the request.")
                return {"status": "invalid signature"}

    # ✅ Zoom URL validation
    if event_type == "endpoint.url_validation":
        token = event_data.get("payload", {}).get("plainToken")
        logger.info("✅ Zoom URL validation succeeded. Returning plainToken.")
        return JSONResponse(content={"plainToken": token})

    # 📌 Payload details
    payload = event_data.get("payload", {})
    obj = payload.get("object", {})
    logger.info(f"📊 Details: meeting_id={obj.get('id')} | host_id={obj.get('host_id')} | topic={obj.get('topic')}")
    logger.debug(f"📦 Full payload: {json.dumps(event_data, indent=2)[:1000]}...")

    # 🔍 Events
    events_log = {
        "recording.completed": "🎬 The recording is complete.",
        "recording.started": "⏺️ Recording has started.",
        "recording.stopped": "⏹️ Recording has stopped.",
        "meeting.started": "📡 The meeting has started.",
        "meeting.ended": "🔚 The meeting has ended."
    }
    logger.info(events_log.get(event_type, f"ℹ️ Unhandled event: {event_type}"))

    if event_type != "recording.completed":
        return {"status": "acknowledged", "event": event_type}

    # 📥 Data from the event
    host_id = obj.get("host_id")
    meeting_id = obj.get("id")
    topic = obj.get("topic", "Untitled Meeting")
    start_time = obj.get("start_time")
    duration = obj.get("duration")
    recording_files = obj.get("recording_files", [])

    if not host_id or not meeting_id:
        logger.error("❌ host_id or meeting_id is missing")
        return {"status": "invalid_data"}

    if not recording_files:
        logger.warning("⚠️ There are no recording files")
        return {"status": "no_recordings"}

    logger.info(f"🎥 Found {len(recording_files)} recording files")

    # ⏱️ Status
    status = "ok"
    if duration is not None and duration < 15:
        status = "too_short"
        logger.warning(f"⚠️ The recording is too short: {duration}s")

    # 🔐 Token and password
    recording_password = obj.get("password")
    download_token = event_data.get("download_token") or payload.get("download_token")

    # 🎞️ Primary MP4 file
    download_url = None
    for f in recording_files:
        if f.get("file_type", "").upper() == "MP4":
            download_url = f.get("download_url")
            download_token = download_token or f.get("download_token")
            recording_password = recording_password or f.get("password")
            logger.info(f"✅ Selected MP4 file: {download_url}")
            break

    if not download_url and recording_files:
        logger.warning("⚠️ No MP4 – using the first file as a fallback")
        f = recording_files[0]
        download_url = f.get("download_url")
        download_token = download_token or f.get("download_token")
        recording_password = recording_password or f.get("password")

    # 🧑‍💻 Link host_id to user_id
    try:
        user_query = supabase.table("oauth_tokens") \
            .select("user_id") \
            .eq("provider", "zoom") \
            .eq("provider_user_id", host_id) \
            .eq("is_active", True) \
            .maybe_single().execute()

        user_id = user_query.data.get("user_id") if user_query.data else None
        if user_id:
            logger.info(f"🔗 Linked host_id -> user_id: {user_id}")
        else:
            logger.warning("⚠️ No user_id found for host_id")
    except Exception as e:
        logger.exception(f"❌ Error looking up user_id: {str(e)}")
        user_id = None

    # 🧾 Create the recording row
    recording_data = {
        "zoom_meeting_id": meeting_id,
        "host_id": host_id,
        "topic": topic,
        "start_time": start_time,
        "duration": duration,
        "recording_files": recording_files,
        "download_url": download_url,
        "download_token": download_token or None,
        "password": recording_password or None,
        "status": status,
        "created_at": datetime.utcnow().isoformat(),
        "user_id": user_id
    }

    try:
        if not user_id:
            recording_data.pop("user_id", None)

        missing = [k for k in ["zoom_meeting_id", "user_id"] if not recording_data.get(k)]
        if missing:
            logger.error(f"❌ Required fields are missing: {missing}")
            return {"status": "error", "missing_fields": missing}

        result = supabase.table("zoom_recordings").insert(recording_data).execute()
        logger.info(f"✅ Zoom recording saved in Supabase:\n{json.dumps(result.data, indent=2)}")
    except Exception as e:
        logger.exception(f"❌ Supabase insert error: {str(e)}")

    # Celery
    try:
        recording_id = result.data[0]["id"] if result.data else None
        if not recording_id:
            raise ValueError("❌ The recording id from Supabase is missing!")

        task_payload = {
            "id": recording_id,
            "host_id": host_id,
            "zoom_meeting_id": meeting_id,
            "topic": topic,
            "start_time": start_time,
            "duration": duration,
            "recording_files": recording_files,
            "download_url": download_url,
            "download_token": download_token,
            "password": recording_password,
            "status": status,
            "received_at": datetime.utcnow().isoformat()
        }

        handle_zoom_recording.delay(task_payload)
        logger.info("🚀 Celery task queued")
    except Exception as e:
        logger.exception(f"❌ Error sending to Celery: {str(e)}")

    return {"status": "queued", "event": event_type}
