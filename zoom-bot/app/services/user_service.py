# app/services/user_service.py
import os
from dotenv import load_dotenv
from app.core.logger import logger
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def get_supabase_client():
    """
    Initialize and return a Supabase client.
    """

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


async def get_user_email_from_supabase(user_id: str) -> str:
    """
    Return the email address for a user_id from the users table.
    """
    try:
        supabase = get_supabase_client()
        response = supabase.table("users").select("email").eq("id", user_id).maybe_single().execute()

        if response.data and "email" in response.data:
            email = response.data["email"]
            logger.info(f"📧 Found email for user {user_id}: {email}")
            return email
        else:
            logger.warning(f"⚠️ No email found for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"❌ Error fetching user email from Supabase: {str(e)}")
        return None


async def get_user_id_from_supabase(host_id: str) -> str | None:
    try:
        supabase = get_supabase_client()
        result = supabase.table("oauth_tokens") \
            .select("user_id") \
            .eq("provider", "zoom") \
            .eq("provider_user_id", host_id) \
            .maybe_single() \
            .execute()

        return result.data.get("user_id") if result.data else None
    except Exception as e:
        logger.error(f"❌ Error fetching user_id for host_id {host_id}: {str(e)}")
        return None


async def save_recording_metadata_to_supabase(recording_data: dict) -> bool:
    try:
        supabase = get_supabase_client()
        response = supabase.table("zoom_recordings").insert(recording_data).execute()
        logger.info(f"💾 Recording saved in Supabase: {response}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving to Supabase: {str(e)}")
        return False
