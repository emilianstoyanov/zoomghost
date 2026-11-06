import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def send_test_zoom_recording_event():
    url = os.getenv("AWS_ZOOM_WEBHOOK_URL")
    download_url = os.getenv("ZOOM_TEST_DOWNLOAD_URL")
    if not url or not download_url:
        raise SystemExit("Set AWS_ZOOM_WEBHOOK_URL and ZOOM_TEST_DOWNLOAD_URL.")

    test_payload = {
        "event": "recording.completed",
        "payload": {
            "object": {
                "id": "test-meeting-123",
                "recording_files": [
                    {
                        "download_url": download_url,
                        "file_type": "mp4"
                    }
                ],
                "download_token": ""
            }
        }
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PostmanRuntime/7.43.3",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=test_payload, headers=headers)

        if response.status_code == 200:
            print("✅ Successfully sent test webhook to AWS endpoint!")
            print("🔁 Response:", response.text)
        else:
            print(f"❌ Failed with status {response.status_code}: {response.text}")


if __name__ == "__main__":
    asyncio.run(send_test_zoom_recording_event())
