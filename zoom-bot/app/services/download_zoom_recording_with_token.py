import os
import aiohttp
from urllib.parse import urlparse
from app.logging_config import setup_logger

logger = setup_logger(__name__)


async def download_zoom_recording_with_token(download_url: str, meeting_id: str, file_type: str = "mp4") -> str:
    """
    Downloads a Zoom-protected recording file using the original access_token in the URL.

    Args:
        download_url: The full Zoom-protected URL (with access_token).
        meeting_id: The meeting ID used to name the downloaded file.
        file_type: Expected file extension from Zoom webhook (e.g., "mp4")

    Returns:
        The path to the downloaded file.
    """
    try:
        logger.info("📌 Using download_url as received from Zoom webhook.")

        # 🔍 Extract file extension safely from path or fallback to file_type
        parsed_url = urlparse(download_url)
        path = parsed_url.path
        extension = (os.path.splitext(path)[1].lstrip(".") or file_type).lower()

        filename = f"/tmp/{meeting_id}.{extension}"
        logger.info(f"💾 Will save file as: {filename}")

        headers = {
            "User-Agent": "Mozilla/5.0",  # ✅ Important for Zoom CDN
            "Accept": "*/*"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            logger.info(f"🔗 Downloading Zoom file for meeting {meeting_id}")
            logger.debug(f"➡️ Requesting URL: {download_url}...")

            async with session.get(download_url) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"❌ Initial download failed. Status code: {resp.status}, Response: {error_text}")
                    raise Exception(f"❌ Failed to download Zoom file. Status code: {resp.status}")
                content = await resp.read()

        with open(filename, "wb") as f:
            f.write(content)

        file_size = os.path.getsize(filename)
        logger.info(f"✅ Zoom recording saved to {filename} ({file_size} bytes)")
        return filename

    except Exception as e:
        logger.error(f"❌ Error downloading Zoom protected file: {str(e)}")
        raise Exception(f"Error downloading Zoom protected file: {str(e)}")
