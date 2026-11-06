import asyncio
import os

from dotenv import load_dotenv

from utils.refresh_zoom_token import refresh_zoom_token

load_dotenv()

user_id = os.getenv("SUPABASE_USER_ID")


async def main():
    if not user_id:
        raise SystemExit("Set SUPABASE_USER_ID.")
    token = await refresh_zoom_token(user_id)
    print("🔐 Refreshed token:\n", token)


if __name__ == "__main__":
    asyncio.run(main())
