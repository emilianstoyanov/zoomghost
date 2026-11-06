# app/services/zoom_token_service.py
import os
import base64
import aiohttp
import logging
import requests
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_datetime

logger = logging.getLogger(__name__)

load_dotenv()
ZOOM_S2S_CLIENT_ID = os.getenv("ZOOM_S2S_CLIENT_ID")
ZOOM_S2S_CLIENT_SECRET = os.getenv("ZOOM_S2S_CLIENT_SECRET")
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_cached_token = None
_cached_token_expiry = None

# Initialize the Supabase client
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    logger.warning("⚠️ SUPABASE_URL or SUPABASE_KEY is missing. Supabase will not be used.")


def encode_client_credentials(client_id: str, client_secret: str) -> str:
    credentials = f"{client_id}:{client_secret}"
    return base64.b64encode(credentials.encode()).decode()


async def get_zoom_access_token() -> str:
    try:
        url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"
        headers = {
            "Authorization": f"Basic {encode_client_credentials(ZOOM_S2S_CLIENT_ID, ZOOM_S2S_CLIENT_SECRET)}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        logger.info("[ZOOM TOKEN] Requesting new access token from Zoom...")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"❌ [ZOOM TOKEN] Failed to get access token. Status: {resp.status}, Response: {text}")
                    raise Exception(f"Failed to get access token. Status: {resp.status}, Response: {text}")

                data = await resp.json()
                logger.info("✅ [ZOOM TOKEN] Successfully retrieved new access token.")
                return data["access_token"]

    except Exception as e:
        logger.exception(f"❌ [ZOOM TOKEN] Error while getting access token: {str(e)}")
        raise


async def get_zoom_token_cached() -> str:
    global _cached_token, _cached_token_expiry

    if _cached_token and _cached_token_expiry and datetime.utcnow() < _cached_token_expiry:
        logger.info("[ZOOM TOKEN] Using cached access token.")
        return _cached_token

    logger.info("[ZOOM TOKEN] No valid cached token, requesting new one...")
    token = await get_zoom_access_token()

    _cached_token = token
    _cached_token_expiry = datetime.utcnow() + timedelta(minutes=55)

    return token


def generate_server_to_server_token() -> str:
    """
    Generate a Zoom Server-to-Server token and store it in Supabase.
    """
    if not ZOOM_S2S_CLIENT_ID or not ZOOM_S2S_CLIENT_SECRET or not ZOOM_ACCOUNT_ID:
        logger.error("❌ [ZOOM TOKEN] Missing credentials in environment variables.")
        return None

    url = "https://zoom.us/oauth/token"
    auth = (ZOOM_S2S_CLIENT_ID, ZOOM_S2S_CLIENT_SECRET)

    data = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        logger.info("🔐 [ZOOM TOKEN] Generating S2S access token...")
        response = requests.post(url, auth=auth, data=data, headers=headers)

        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)

            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            if supabase:
                token_record = {
                    "id": "zoom-global-token-s2s",
                    "access_token": access_token,
                    "refresh_token": None,
                    "expires_at": expires_at.isoformat(timespec="seconds"),  # ✅ Safe ISO format
                    "scope": token_data.get("scope", ""),
                    "token_type": token_data.get("token_type", "bearer")
                }

                logger.info("📥 [ZOOM TOKEN] Saving the new token to Supabase...")
                supabase.table("zoom_tokens").upsert(token_record).execute()
                logger.info("✅ [ZOOM TOKEN] Supabase updated with new token.")

            return access_token

        else:
            logger.error(f"❌ [ZOOM TOKEN] Failed to get token: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.exception(f"❌ [ZOOM TOKEN] Exception during token generation: {str(e)}")
        return None


# ✅ Central function that returns a token safely
def get_valid_zoom_token(force_refresh: bool = False) -> str:
    """
    Return a valid Zoom S2S token. Uses Supabase as a cache and refreshes the token when needed.

    Args:
        force_refresh (bool): When True, always fetch a new token

    Returns:
        str: Valid access_token
    """
    if not supabase:
        raise Exception("❌ Supabase client is not initialized.")

    try:
        if not force_refresh:
            result = supabase.table("zoom_tokens").select("*").limit(1).execute()
            tokens = result.data
            if tokens:
                token = tokens[0]
                expires_at = parse_datetime(token.get("expires_at", "2000-01-01T00:00:00"))
                if expires_at > datetime.utcnow() + timedelta(minutes=2):
                    logger.info("✅ [Zoom Token] Using the cached token from Supabase")
                    return token.get("access_token")

        logger.info("🔁 [Zoom Token] Fetching a new token from Zoom...")
        new_token = generate_server_to_server_token()
        if not new_token:
            raise Exception("❌ Failed to fetch a new Zoom token.")

        return new_token

    except Exception as e:
        logger.error(f"❌ [Zoom Token] Error while fetching the token: {str(e)}")
        raise
