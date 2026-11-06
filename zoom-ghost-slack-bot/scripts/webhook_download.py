import os

import httpx
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("ZOOM_WEBHOOK_DOWNLOAD_URL")
download_token = os.getenv("ZOOM_WEBHOOK_DOWNLOAD_TOKEN")
if not url or not download_token:
    raise SystemExit("Set ZOOM_WEBHOOK_DOWNLOAD_URL and ZOOM_WEBHOOK_DOWNLOAD_TOKEN.")

full_url = f"{url}?access_token={download_token}"

with httpx.Client(timeout=10.0) as client:
    response = client.head(full_url)
    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("content-type"))
