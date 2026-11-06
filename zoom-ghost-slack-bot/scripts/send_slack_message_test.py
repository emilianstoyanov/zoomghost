import logging
import os

from dotenv import load_dotenv

from tasks.slack_tasks import send_slack_message

load_dotenv()

logging.basicConfig(level=logging.INFO)

slack_user_id = os.getenv("SLACK_TEST_USER_ID")
user_access_token = os.getenv("SLACK_TEST_TOKEN") or os.getenv("SLACK_BOT_TOKEN")

test_text = "🔔 *Test message from a Python script!*"
blocks = [
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Test:* This is a markdown block from a local test 🚀"
        }
    }
]

if __name__ == "__main__":
    if not slack_user_id or not user_access_token:
        raise SystemExit("Set SLACK_TEST_USER_ID and SLACK_BOT_TOKEN (or SLACK_TEST_TOKEN).")
    print("📤 Sending a test Slack message...")
    ts = send_slack_message(
        slack_user_id=slack_user_id,
        text=test_text,
        blocks=blocks,
        token=user_access_token
    )

    if ts:
        print(f"✅ Sent successfully. Timestamp: {ts}")
    else:
        print("❌ Send failed.")
