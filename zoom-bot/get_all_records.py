import asyncio
import httpx
import os
from datetime import datetime, timedelta
from typing import Dict

from dotenv import load_dotenv
from fastapi import HTTPException
from supabase import create_client, Client

load_dotenv()

zoom_token_cache: Dict[str, Dict] = {}
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


async def get_zoom_recordings(user_id: str):
    print("🔄 Refreshing token...")
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

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(base_url, headers=headers, params=params)
            if response.status_code != 200:
                print(f"❌ Error: {response.status_code} - {response.text}")
                return

            data = response.json()
            meetings = data.get("meetings", [])

            if not meetings:
                print("ℹ️ No more recordings found.")
                break

            print(f"✅ Found {len(meetings)} recordings on this page:\n")

            for meeting in meetings:
                print(f"📅 Topic: {meeting.get('topic')}")
                print(f"🕒 Start Time: {meeting.get('start_time')}")
                print(f"🔗 Playback URL: {meeting.get('share_url')}")

                for file in meeting.get("recording_files", []):
                    file_type = file.get("file_type")
                    download_url = file.get("download_url")
                    if file_type and download_url:
                        print(f"📥 {file_type} ➜ {download_url}?access_token={access_token}")
                print("-" * 40)

            # Check for next page
            next_page_token = data.get("next_page_token")
            print(f"➡️ next_page_token: {next_page_token}")
            if not next_page_token:
                break

            params["next_page_token"] = next_page_token

async def refresh_zoom_token(user_id: str) -> str:
    """Returns a valid Zoom access token, refreshing if needed."""

    now = datetime.utcnow()
    print("\n🔄 [Zoom Token] Checking token for user_id:", user_id)

    # 1. Check the local cache
    cached = zoom_token_cache.get(user_id)
    if cached:
        print("⚡ Found in local cache.")
        print("🕒 Now:", now.isoformat())
        print("📅 Expires at (cached):", cached['expires_at'].isoformat())

        if cached["expires_at"] > now:
            print("✅ Token is still valid. Returning from cache.")
            print("🔐 Token (start):", cached["access_token"][:30] + "...[redacted]")
            return cached["access_token"]
        else:
            print("⏰ Cached token is expired. Will refresh.")

    # 2. Read from Supabase
    print("📡 Fetching from Supabase...")
    res = supabase.table("oauth_tokens").select("*") \
        .eq("user_id", user_id).eq("provider", "zoom").eq("is_active", True) \
        .maybe_single().execute()
    token_data = res.data

    if not token_data:
        raise HTTPException(status_code=404, detail="Zoom token not found for user.")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_at_str = token_data.get("expires_at")
    print("🔍 raw expires_at from Supabase:", expires_at_str)
    expires_at = safe_parse_datetime(expires_at_str) if expires_at_str else now - timedelta(seconds=1)

    print("🕒 Now:", now.isoformat())
    print("📅 Expires at (supabase):", expires_at.isoformat())

    if expires_at > now:
        print("✅ Token is valid (from Supabase). Caching.")
        zoom_token_cache[user_id] = {"access_token": access_token, "expires_at": expires_at}
        print("🔐 Token (start):", access_token[:30] + "...[redacted]")
        return access_token

    # 3. Refresh the token
    print("♻️ Refreshing token via Zoom OAuth...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://zoom.us/oauth/token",
            params={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        new_data = response.json()
        new_token = new_data["access_token"]
        new_refresh = new_data["refresh_token"]
        new_expiration = now + timedelta(seconds=new_data["expires_in"])

        print("✅ Token refreshed successfully.")
        print("📅 New expiration:", new_expiration.isoformat())
        print("🔐 New token refreshed.")

        # 4. Save to Supabase
        supabase.table("oauth_tokens").update({
            "access_token": new_token,
            "refresh_token": new_refresh,
            "expires_at": new_expiration.isoformat()
        }).eq("id", token_data["id"]).execute()

        # 5. Cache it
        zoom_token_cache[user_id] = {"access_token": new_token, "expires_at": new_expiration}
        print("💾 Updated Supabase + local cache.")

        return new_token

if __name__ == "__main__":
    user_id = os.getenv("SUPABASE_USER_ID")
    if not user_id:
        raise SystemExit("Set SUPABASE_USER_ID.")
    asyncio.run(get_zoom_recordings(user_id))
