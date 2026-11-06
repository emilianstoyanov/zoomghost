import asyncio
import httpx
from datetime import datetime, timedelta
from utils.refresh_zoom_token import refresh_zoom_token


async def get_zoom_recordings(user_id: str) -> list:
    access_token = await refresh_zoom_token(user_id)

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    base_url = "https://api.zoom.us/v2/users/me/recordings"
    params = {
        "page_size": 30,
        "from": (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d"),
        "to": datetime.utcnow().strftime("%Y-%m-%d")
    }

    all_meetings = []

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(base_url, headers=headers, params=params)
            if response.status_code != 200:
                raise Exception(f"❌ Zoom API Error {response.status_code} - {response.text}")

            data = response.json()
            meetings = data.get("meetings", [])

            for meeting in meetings:
                meeting["access_token"] = access_token  # ⬅️ Attach the token in case it is needed later
                all_meetings.append(meeting)

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break
            params["next_page_token"] = next_page_token

    return all_meetings
