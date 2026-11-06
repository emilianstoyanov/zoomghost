# app/utils/refresh_zoom_token.py
import os
import httpx
from fastapi import HTTPException
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Dict
from datetime import datetime, timedelta

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Local cache: { user_id: { access_token, expires_at } }
zoom_token_cache: Dict[str, Dict] = {}


def safe_parse_datetime(dt_str: str) -> datetime:
    """Safely parse datetime string even if microseconds are missing or short."""
    try:
        if "." in dt_str:
            base, micro = dt_str.split(".")
            micro = (micro + "000000")[:6]  # always 6 digits
            dt_str = f"{base}.{micro}"
        return datetime.fromisoformat(dt_str)
    except Exception as e:
        print(f"❌ [safe_parse_datetime] Error parsing '{dt_str}': {e}")
        return datetime.utcnow()


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
        print("🔐 New token (start):", new_token[:30] + "...[redacted]")

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
