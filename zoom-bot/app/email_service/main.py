# email_service\main.py
import asyncio
import os

from app.email_service.sender_async import send_email_async

recipient_email = os.getenv("USER_EMAIL")


async def main():
    if not recipient_email:
        raise SystemExit("Set USER_EMAIL to the recipient address.")
    await send_email_async(
        recipient_email=recipient_email,
        subject="🔔 Test Email",
        body="This is a test message from ZoomBot (async)."
    )


if __name__ == "__main__":
    asyncio.run(main())
