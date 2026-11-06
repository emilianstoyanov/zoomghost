import asyncio
import logging
from datetime import datetime, timedelta
from app.services.zoom_token_service import generate_server_to_server_token, supabase

logger = logging.getLogger(__name__)


async def token_refresher_loop(interval_minutes=50):
    """
    Background loop that checks whether the token will expire soon
    and, when needed, generates a new Zoom access_token.
    """
    while True:
        try:
            logger.info("🔄 [Token Refresher] Checking the Zoom token...")

            if not supabase:
                logger.warning("⚠️ [Token Refresher] No Supabase client.")
                await asyncio.sleep(interval_minutes * 60)
                continue

            response = supabase.table("zoom_tokens").select("*").limit(1).execute()
            tokens = response.data

            if tokens:
                token_data = tokens[0]
                expires_at_str = token_data.get("expires_at", "2000-01-01T00:00:00")

                try:
                    # ⏱️ Reliable date parsing
                    expires_at = datetime.fromisoformat(expires_at_str)
                except ValueError:
                    logger.warning("⚠️ [Token Refresher] ISO format problem, using the fallback parser.")
                    expires_at = datetime.strptime(expires_at_str, "%Y-%m-%dT%H:%M:%S.%f")

                # 🔄 If the token expires soon
                if expires_at < datetime.utcnow() + timedelta(minutes=10):
                    logger.warning("⏳ [Token Refresher] The token expires soon. Generating a new one...")
                    generate_server_to_server_token()
                else:
                    logger.info("✅ [Token Refresher] The token is still valid.")
            else:
                logger.warning("⚠️ [Token Refresher] No token found. Generating a new one...")
                generate_server_to_server_token()

        except Exception as e:
            logger.error(f"❌ [Token Refresher] Error: {str(e)}")

        await asyncio.sleep(interval_minutes * 60)
