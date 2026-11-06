import os
import logging
import requests
from dotenv import load_dotenv
from app.services.zoom_token_service import get_valid_zoom_token

load_dotenv()
logger = logging.getLogger(__name__)


def get_recording_download_url(meeting_id):
    """
    Return a direct download URL for a Zoom recording, with the access token included
    """
    token = get_valid_zoom_token()
    if not token:
        print(f"❌ [ZOOM API] Could not get a valid token for {meeting_id}")
        return None

    if not meeting_id.isdigit() and "-" in meeting_id:
        try:
            print(f"[ZOOM API] Custom ID detected: {meeting_id}, trying as is")
        except Exception as e:
            print(f"[ZOOM API] Error looking up meeting ID: {str(e)}")

    url = f"https://api.zoom.us/v2/meetings/{meeting_id}/recordings"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            recording_data = response.json()
            files = []
            recording_files = recording_data.get("recording_files", [])

            for file in recording_files:
                download_url = file.get("download_url")

                if download_url:
                    if "?" in download_url:
                        download_url += f"&access_token={token}"
                    else:
                        download_url += f"?access_token={token}"
                    download_url += "&download=1"

                files.append({
                    "id": file.get("id"),
                    "file_type": file.get("file_type"),
                    "download_url": download_url,
                    "recording_start": file.get("recording_start"),
                    "recording_end": file.get("recording_end"),
                    "file_size": file.get("file_size")
                })

            print(f"✅ [ZOOM API] Successfully received {len(files)} files for {meeting_id}")
            return files

        else:
            print(f"❌ [ZOOM API] HTTP Error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"❌ [ZOOM API] Exception during the API request: {str(e)}")
        return None


def download_meeting_recording(meeting_id, preferred_type="mp4", passcode=None):
    """
    Downloads a recording from Zoom API using proper authentication

    Returns:
        Tuple of (file_path, file_type) or (None, None) if download fails
    """
    try:
        recording_files = get_recording_download_url(meeting_id)

        if not recording_files:
            print(f"[ZOOM API] No recording files found for meeting {meeting_id}")
            return None, None

        preferred_files = [f for f in recording_files if f.get('file_type', '').lower() == preferred_type.lower()]
        files_to_try = preferred_files if preferred_files else recording_files

        for file_info in files_to_try:
            download_url = file_info.get('download_url')
            file_type = file_info.get('file_type', '').upper()

            if not download_url:
                continue

            print(f"[ZOOM API] Attempting to download {file_type} recording...")

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }

            response = requests.get(download_url, headers=headers, allow_redirects=True)

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')

                if 'text/html' in content_type:
                    print("[ZOOM API] Received HTML instead of file - skipping")
                    continue

                ext = file_type.lower()
                if 'video/mp4' in content_type:
                    ext = 'mp4'
                elif 'audio/mp4' in content_type or 'audio/x-m4a' in content_type:
                    ext = 'm4a'
                elif 'audio/mpeg' in content_type:
                    ext = 'mp3'

                temp_dir = os.getenv("TEMP_DIR", "/tmp")
                os.makedirs(temp_dir, exist_ok=True)

                file_path = os.path.join(temp_dir, f"{meeting_id}.{ext}")

                with open(file_path, 'wb') as f:
                    f.write(response.content)

                print(f"[ZOOM API] Successfully downloaded recording to {file_path}")
                return file_path, file_type

            else:
                print(f"[ZOOM API] Download failed: {response.status_code}")
                print(f"[ZOOM API] Response: {response.text[:200]}...")

        print("[ZOOM API] All download attempts failed")
        return None, None

    except Exception as e:
        print(f"[ZOOM API] Error downloading recording: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None, None
