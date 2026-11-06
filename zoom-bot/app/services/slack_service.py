# app/services/slack_service.py

import os
from datetime import datetime
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

if DEBUG:
    print("🔐 [DEBUG] SLACK_BOT_TOKEN (masked):", SLACK_TOKEN[:6] + "..." if SLACK_TOKEN else "None")

client = WebClient(token=SLACK_TOKEN)


def send_summary_to_slack(summary: str, meeting_id: str, channel_id: str) -> bool:
    if not SLACK_TOKEN or not channel_id:
        print("❌ [SLACK] Missing SLACK_BOT_TOKEN or dynamic channel_id")
        return False

    message = f"*📋 Summary for meeting `{meeting_id}`:*\n\n{summary}"

    if DEBUG:
        print("📨 [DEBUG] Slack message length:", len(message))
        print("📨 [DEBUG] Sending to channel:", channel_id)

    if len(message) > 3900:
        print("⚠️ [SLACK] Summary too long → sending as file instead...")
        return send_file_to_slack([summary], meeting_id, channel_id, label="📋 Full summary (fallback)")

    try:
        response = client.chat_postMessage(channel=channel_id, text=message)

        if DEBUG:
            print("📨 [DEBUG] Slack response:", response.data)

        if response.get("ok"):
            print("✅ [SLACK] Summary sent successfully.")
            return True
        else:
            error = response.get("error", "unknown_error")
            print(f"❌ [SLACK] Error: {error}")

            # 📛 Common cases to watch for
            if error in ["channel_not_found", "not_in_channel", "invalid_auth", "account_inactive"]:
                print("⚠️ [SLACK] Critical error – possible uninstalled bot or missing permissions.")

            return False

    except SlackApiError as e:
        print(f"❌ [SLACK] API Error: {e.response['error']}")
        return False


def send_file_to_slack(content_blocks: list[str], meeting_id: str, channel_id: str, label: str) -> bool:
    if not SLACK_TOKEN or not channel_id:
        print("❌ [SLACK] Missing SLACK_BOT_TOKEN or dynamic channel_id")
        return False

    try:
        content = "\n\n---\n\n".join(content_blocks)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{label.lower().replace(' ', '-')}-{meeting_id}-{timestamp}.txt"
        filepath = os.path.join("/tmp", filename)

        if DEBUG:
            print(f"📁 [DEBUG] Writing file: {filepath}")
            print(f"📁 [DEBUG] Content length: {len(content)}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        with open(filepath, "rb") as file_data:
            upload = client.files_upload_v2(
                channel=channel_id,
                initial_comment=f"{label} for *{meeting_id}* 📎",
                file_uploads=[{
                    "file": file_data,
                    "filename": filename,
                    "title": f"{label} for meeting {meeting_id}"
                }]
            )

        os.remove(filepath)

        if DEBUG:
            print(f"📁 [DEBUG] Upload response: {upload.data}")

        if upload.get("ok"):
            print(f"📎 [SLACK] File sent: {filename}")
            return True
        else:
            error = upload.get("error", "unknown_error")
            print(f"❌ [SLACK] Upload failed: {error}")

            if error in ["channel_not_found", "not_in_channel", "invalid_auth"]:
                print("⚠️ [SLACK] File upload failed due to permission or access issues.")

            return False

    except SlackApiError as e:
        print(f"❌ [SLACK] File upload failed: {e.response['error']}")
        return False
    except Exception as e:
        print(f"❌ [SLACK] Unexpected error: {e}")
        return False


def send_all_slack_files(meeting_id: str, full_summary: str, chunked_summaries: list[str], transcript: str,
                         channel_id: str) -> None:
    print("📤 [SLACK] Sending all summary components...")

    if DEBUG:
        print(f"🧪 [DEBUG] Summary length: {len(full_summary)}")
        print(f"🧪 [DEBUG] Chunked summaries count: {len(chunked_summaries)}")
        print(f"🧪 [DEBUG] Transcript length: {len(transcript)}")
        print(f"📢 [DEBUG] Target Slack channel: {channel_id}")

    if not send_file_to_slack([full_summary], meeting_id, channel_id, label="📋 Full summary"):
        print("⚠️ Could not send full summary to Slack.")

    if len(chunked_summaries) > 1:
        if not send_file_to_slack(chunked_summaries, meeting_id, channel_id, label="🔍 Chunked summary"):
            print("⚠️ Could not send chunked summary to Slack.")

    if not send_file_to_slack([transcript], meeting_id, channel_id, label="📜 Transcript"):
        print("⚠️ Could not send transcript to Slack.")
