# app/services/download_file_directly.py

import os
import requests
import logging
import tempfile

logger = logging.getLogger(__name__)

import urllib.parse


async def download_file_directly(download_url: str, meeting_id: str) -> str:
    """
    Improved: Downloads a file from URL. If 'access_token' is detected, uses Bearer Authorization.
    """
    try:
        logger.info(f"[DOWNLOAD] Trying to download from public URL: {download_url}")

        # Detect access token
        parsed_url = urllib.parse.urlparse(download_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        access_token = query_params.get('access_token', [None])[0]

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/113.0.0.0 Safari/537.36"
            )
        }

        if access_token:
            logger.info("[DOWNLOAD] Detected access_token in URL. Using Authorization header.")
            headers["Authorization"] = f"Bearer {access_token}"

            # Remove token from URL (Zoom expects Authorization header, not URL param)
            download_url = download_url.split('?')[0]

        response = requests.get(download_url, headers=headers, stream=True, timeout=30)

        logger.info(f"[DOWNLOAD] HTTP Status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"[DOWNLOAD] Failed with status code: {response.status_code}")
            logger.error(f"[DOWNLOAD] Response (truncated): {response.text[:200]}...")
            return None

        content_type = response.headers.get('Content-Type', '').lower()
        logger.info(f"[DOWNLOAD] Content-Type: {content_type}")

        if 'html' in content_type:
            logger.error("[DOWNLOAD] Received HTML instead of media file. Aborting.")
            return None

        # Save file as before
        temp_dir = os.getenv("TEMP_DIR", "/tmp")
        os.makedirs(temp_dir, exist_ok=True)
        ext = detect_extension(content_type) or "bin"
        file_path = os.path.join(temp_dir, f"{meeting_id}.{ext}")

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"[DOWNLOAD] Successfully downloaded file: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"[DOWNLOAD ERROR] {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def detect_extension(content_type: str) -> str:
    """
    Detects appropriate file extension based on content type.
    """
    if "audio/mpeg" in content_type:
        return "mp3"
    elif "audio/mp4" in content_type or "audio/x-m4a" in content_type:
        return "m4a"
    elif "audio/wav" in content_type:
        return "wav"
    elif "video/mp4" in content_type:
        return "mp4"
    elif "application/octet-stream" in content_type:
        return "bin"
    else:
        logger.warning(f"[DOWNLOAD] Unknown Content-Type: {content_type}")
        return None
