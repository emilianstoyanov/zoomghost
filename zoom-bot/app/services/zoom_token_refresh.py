# app/services/zoom_token_refresh.py
import httpx
from app.services.zoom_token_service import get_valid_zoom_token


async def refresh_zoom_download_url(host_id: str, meeting_id: str, file_type: str = "MP4") -> str:
    try:
        access_token = get_valid_zoom_token(force_refresh=True)
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        url = f"https://api.zoom.us/v2/meetings/{meeting_id}/recordings"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code != 200:
            return None

        data = resp.json()
        for f in data.get("recording_files", []):
            if f.get("file_type", "").upper() == file_type and f.get("download_url"):
                return f"{f['download_url']}?access_token={access_token}"

    except Exception as e:
        from app.logging_config import setup_logger
        logger = setup_logger(__name__)
        logger.error(f"❌ [ZOOM REFRESH] Error refreshing download URL: {str(e)}")

    return None
