# app/services/zoom_service.py
import os
import httpx
import traceback
from datetime import datetime
from app.core.logger import logger
from app.services.summarizer import summarize_transcript
from app.services.user_service import get_user_id_from_supabase
from app.services.user_service import get_user_email_from_supabase
from app.services.zoom_token_refresh import refresh_zoom_download_url
from app.services.download_file_directly import download_file_directly
from app.services.transcriber import transcribe_audio, split_audio_file
from app.services.user_service import save_recording_metadata_to_supabase
from app.services.slack_service import send_summary_to_slack, send_all_slack_files
from app.email_service.sender_async import render_summary_email, send_email_with_attachment
from app.services.download_zoom_recording_with_token import download_zoom_recording_with_token


async def process_zoom_recording(
        meeting_id: str,
        host_id: str = None,
        topic: str = None,
        start_time: str = None,
        recording_files: list = None,
        channel_id: str = None
):
    result = {
        "success": False,
        "meeting_id": meeting_id,
        "error": None
    }

    temp_files = []

    try:
        logger.info(f"[PROCESSING] Started processing meeting {meeting_id}")
        logger.info(f"🧾 Context: host_id={host_id}, channel_id={channel_id}")

        file_path = None
        file_type = None

        # --- 1. Download recording ---
        if recording_files:
            logger.info(f"[PROCESSING] Found {len(recording_files)} recording files")
            preferred_order = ["MP4", "M4A", "MP3"]

            for preferred_type in preferred_order:
                for file in recording_files:
                    file_type = file.get("file_type", "").upper()
                    download_url = file.get("download_url")

                    logger.info("🔗 Trying to download file:")
                    logger.info(f"    URL: {download_url}")
                    logger.info(f"    Type: {file_type or 'N/A'}")

                    if (file_type == preferred_type or not file_type) and download_url:
                        try:
                            if "zoom.us" in download_url or "zoomgov.com" in download_url:
                                logger.info("[ZOOM API] Protected URL, using access token...")
                                try:
                                    file_path = await download_zoom_recording_with_token(download_url, meeting_id,
                                                                                         file_type)
                                except Exception as e:
                                    if "401" in str(e) or "403" in str(e):
                                        logger.warning("🔁 Token might be expired, trying to refresh...")
                                        refreshed_url = await refresh_zoom_download_url(host_id, meeting_id, file_type)
                                        if refreshed_url:
                                            file_path = await download_zoom_recording_with_token(refreshed_url,
                                                                                                 meeting_id, file_type)
                                        else:
                                            raise Exception("❌ Failed to refresh Zoom URL or token.")
                                    else:
                                        raise
                            else:
                                logger.info("[PROCESSING] Public URL, downloading directly...")
                                file_path = await download_file_directly(download_url, meeting_id)

                            if file_path:
                                logger.info(f"✅ File downloaded to {file_path}")
                                logger.info(f"📦 File size: {os.path.getsize(file_path)} bytes")
                                break
                            else:
                                logger.error("❌ File download returned None")
                        except Exception as e:
                            logger.error(f"❌ Exception during download: {str(e)}")

                if file_path:
                    break

            if not file_path:
                for file in recording_files:
                    download_url = file.get("download_url")
                    fallback_type = file.get("file_type", "N/A")
                    if not download_url:
                        continue

                    logger.info(f"🔍 Fallback file type: {fallback_type}")
                    logger.info(f"🔄 Final fallback attempt to download: {download_url}")
                    try:
                        file_path = await download_file_directly(download_url, meeting_id)
                        if file_path:
                            logger.info(f"✅ File downloaded (fallback) to {file_path}")
                            break
                    except Exception as e:
                        logger.warning(f"⚠️ Fallback download failed: {str(e)}")

        # --- 2. Validate file existence ---
        if not file_path or not os.path.exists(file_path):
            raise Exception("❌ Download failed or file not found.")

        file_size = os.path.getsize(file_path)
        logger.info(f"📦 Downloaded file size: {file_size} bytes")

        # --- 3. Transcription ---
        transcript = ""
        if file_size > 25 * 1024 * 1024:
            logger.warning("⚠️ File too large, splitting...")
            audio_chunks = split_audio_file(file_path)
            logger.info(f"🔹 Split into {len(audio_chunks)} chunks.")

            for idx, chunk in enumerate(audio_chunks):
                try:
                    logger.info(f"🎙️ Transcribing chunk {idx + 1}/{len(audio_chunks)}: {chunk}")
                    chunk_transcript = transcribe_audio(chunk)
                    transcript += chunk_transcript + "\n"
                    os.remove(chunk)
                except Exception as e:
                    logger.error(f"❌ Error transcribing chunk {chunk}: {str(e)}")
        else:
            logger.info("🎙️ Transcribing full file")
            transcript = transcribe_audio(file_path)

        if not transcript.strip():
            raise Exception("❌ Empty transcript after processing.")

        logger.info(f"[TRANSCRIBE RESULT] Transcript preview:\n{transcript[:1000]}...")

        # --- 4. Summarization ---
        summary, chunk_summaries = summarize_transcript(transcript)

        if not summary.strip():
            raise Exception("❌ Summary generation failed.")

        logger.info(f"[SUMMARY] Generated summary with {len(summary)} characters.")
        logger.info(f"[SUMMARY RESULT] Final summary:\n{summary}")

        # --- 5. Slack Sending ---
        if channel_id:
            logger.info(f"📤 Sending to Slack channel: {channel_id}")
            try:
                send_summary_to_slack(summary, meeting_id, channel_id)
                send_all_slack_files(meeting_id, summary, chunk_summaries, transcript, channel_id)
                logger.info(f"✅ Slack summary sent to {channel_id}")
            except Exception as slack_err:
                logger.warning(f"⚠️ Slack delivery failed: {str(slack_err)}")
        else:
            logger.warning("⚠️ channel_id is missing – skipping Slack delivery.")

        # --- 6. Email Sending ---
        if host_id:
            try:
                logger.info(f"📧 Fetching user email for host_id: {host_id}")
                user_email = await get_user_email_from_supabase(host_id)

                if user_email:
                    logger.info(f"📧 Found user email: {user_email}")
                    body_html = render_summary_email(meeting_id, summary)
                    await send_email_with_attachment(
                        recipient_email=user_email,
                        subject=f"📋 Zoom Meeting Summary: {meeting_id}",
                        body=summary,
                        body_html=body_html,
                        attachment_text=summary,
                        attachment_filename=f"summary-{meeting_id}.txt"
                    )
                    logger.info(f"✅ Email sent to {user_email}")
                else:
                    logger.warning(f"⚠️ No email found for host_id: {host_id}")
            except Exception as email_error:
                logger.error(f"❌ Failed to send summary email: {str(email_error)}")

        # --- 7. Cleanup ---
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logger.info(f"🧹 Deleted temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete temp file {temp_file}: {str(e)}")

        result["success"] = True
        result["summary"] = summary
        result["chunk_summaries"] = chunk_summaries
        result["transcript"] = transcript

    except Exception as e:
        logger.error(f"[PROCESSING ERROR] {str(e)}")
        logger.error(f"[PROCESSING ERROR] Stack trace: {traceback.format_exc()}")
        result["error"] = str(e)

    return result


async def try_download_file(download_url: str) -> bool:
    """
    Try to download a file from a URL to confirm that it is reachable.
    """
    try:
        logger.info(f"🌐 [DOWNLOAD TEST] Checking URL: {download_url[:100]}...")
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(download_url, headers=headers)

        logger.info(f"📡 [DOWNLOAD TEST] Status code: {response.status_code}")
        content_type = response.headers.get('Content-Type', 'unknown')
        logger.info(f"📦 [DOWNLOAD TEST] Content-Type: {content_type}")

        if response.status_code == 200 and 'html' not in content_type.lower():
            logger.info("✅ [DOWNLOAD TEST] Downloadable file confirmed.")
            return True
        else:
            logger.warning("⚠️ [DOWNLOAD TEST] Not a valid downloadable file.")
            return False

    except Exception as e:
        logger.error(f"❌ [DOWNLOAD TEST] Error checking download URL: {str(e)}")
        return False


async def handle_zoom_payload(payload: dict):
    """
    Handle a Zoom webhook payload. Store the metadata and start processing.
    """
    zoom_data = payload.get("payload", {}).get("object", {})

    meeting_id = str(zoom_data.get("id"))
    host_id = zoom_data.get("host_id")
    topic = zoom_data.get("topic", "Untitled Meeting")
    start_time = zoom_data.get("start_time")
    duration = zoom_data.get("duration")
    password = zoom_data.get("password")
    download_token = payload.get("download_token") or zoom_data.get("download_token")
    recording_files = zoom_data.get("recording_files", [])

    logger.info(f"[HANDLE ZOOM PAYLOAD] meeting_id={meeting_id} host_id={host_id}")

    if not meeting_id or not recording_files:
        logger.warning("❌ Missing meeting_id or recording_files in payload.")
        return {"success": False, "error": "Invalid payload."}

    # 🔁 If the password and token are missing, look in recording_files
    if not password:
        for file in recording_files:
            if file.get("password"):
                password = file["password"]
                break

    if not download_token:
        for file in recording_files:
            if file.get("download_token"):
                download_token = file["download_token"]
                break

    # 🔐 Extract the main download_url (for display)
    download_url = None
    for file in recording_files:
        if "download_url" in file:
            download_url = file["download_url"]
            break

    # 🧠 Compute the status (for example, a recording that is too short)
    status = "ok"
    if duration is not None and duration < 15:
        status = "too_short"

    # ✅ Take user_id from the payload when it is present
    user_id = zoom_data.get("user_id")

    # 🔍 If it is missing, fall back to the database (by host_id)
    if not user_id:
        user_id = await get_user_id_from_supabase(host_id)
        if not user_id:
            logger.warning(f"⚠️ No user found for host_id: {host_id}")

    # 💾 Prepare the object to store in Supabase
    recording_data = {
        "zoom_meeting_id": meeting_id,
        "host_id": host_id,
        "topic": topic,
        "start_time": start_time,
        "duration": duration,
        "recording_files": recording_files,
        "download_url": download_url,
        "download_token": download_token,
        "password": password,
        "status": status,
        "created_at": datetime.utcnow().isoformat(),
        "user_id": user_id,
    }

    # 🔍 Turn empty strings into None
    for key in ["download_token", "password"]:
        if recording_data.get(key) == "":
            recording_data[key] = None

    # 🛡️ If user_id is missing and the database requires it, drop the field
    if not user_id:
        logger.warning("⚠️ No user_id – we will try to save the row without it (if that is allowed).")
        recording_data.pop("user_id", None)

    logger.info(f"📝 Saving metadata to Supabase: {recording_data}")
    await save_recording_metadata_to_supabase(recording_data)

    logger.info("✅ Metadata saved. Skipping recording processing.")
    return {
        "success": True,
        "message": "Recording metadata saved to Supabase. No processing triggered."
    }
