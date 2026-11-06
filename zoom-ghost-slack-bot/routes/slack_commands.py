# routes/slack_commands.py
import os
import httpx
from supabase import create_client
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request, Form

router = APIRouter()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# Helper: builds initial option block
def build_initial_option(text, value):
    return {
        "text": {"type": "plain_text", "text": text},
        "value": value
    }


@router.post("/settings")
async def open_settings_modal(
        request: Request,
        trigger_id: str = Form(...),
        user_id: str = Form(...)
):
    # 1. Find the Supabase user id
    res = supabase.table("oauth_tokens").select("user_id") \
        .eq("provider", "slack") \
        .eq("provider_user_id", user_id).maybe_single().execute()

    if not res.data:
        return JSONResponse({"text": "❌ Slack user not linked."}, status_code=400)

    supabase_user_id = res.data["user_id"]

    # 2. Load preferences
    user_data = supabase.table("users").select("preferences") \
        .eq("id", supabase_user_id).maybe_single().execute()

    prefs = user_data.data.get("preferences", {}) if user_data.data else {}

    def opt_val(prefs_key, default_value):
        return prefs.get(prefs_key, default_value)

    # 3. Build the modal view with initial_option
    modal_view = {
        "type": "modal",
        "callback_id": "settings_modal",
        "title": {"type": "plain_text", "text": "ZoomGhost Settings"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "notifications",
                "element": {
                    "type": "static_select",
                    "action_id": "notifications_select",
                    "placeholder": {"type": "plain_text", "text": "Select"},
                    "options": [
                        build_initial_option("Slack", "slack"),
                        build_initial_option("Email", "email"),
                        build_initial_option("Both", "both"),
                        build_initial_option("None", "none"),
                    ],
                    "initial_option": build_initial_option(
                        opt_val("notifications", "Slack").capitalize(),
                        opt_val("notifications", "slack")
                    )
                },
                "label": {"type": "plain_text", "text": "Receive notifications via"}
            },
            {
                "type": "input",
                "block_id": "summaries",
                "element": {
                    "type": "static_select",
                    "action_id": "summaries_select",
                    "placeholder": {"type": "plain_text", "text": "Select"},
                    "options": [
                        build_initial_option("Slack", "slack"),
                        build_initial_option("Email", "email"),
                        build_initial_option("Both", "both"),
                        build_initial_option("None", "none"),
                    ],
                    "initial_option": build_initial_option(
                        opt_val("summaries", "Slack").capitalize(),
                        opt_val("summaries", "slack")
                    )
                },
                "label": {"type": "plain_text", "text": "Receive summaries via"}
            },
            {
                "type": "input",
                "block_id": "auto_process",
                "element": {
                    "type": "static_select",
                    "action_id": "auto_process_select",
                    "placeholder": {"type": "plain_text", "text": "Select"},
                    "options": [
                        build_initial_option("Yes", "true"),
                        build_initial_option("No", "false"),
                    ],
                    "initial_option": build_initial_option(
                        "Yes" if opt_val("auto_process", True) else "No",
                        "true" if opt_val("auto_process", True) else "false"
                    )
                },
                "label": {"type": "plain_text", "text": "Auto-process recordings?"}
            },
            {
                "type": "input",
                "block_id": "min_duration",
                "element": {
                    "type": "static_select",
                    "action_id": "min_duration_select",
                    "placeholder": {"type": "plain_text", "text": "Select"},
                    "options": [
                        build_initial_option("5 min", "5"),
                        build_initial_option("10 min", "10"),
                        build_initial_option("15 min", "15"),
                    ],
                    "initial_option": build_initial_option(
                        f"{opt_val('min_duration', 5)} min",
                        str(opt_val("min_duration", 5))
                    )
                },
                "label": {"type": "plain_text", "text": "Only process if longer than"}
            }
        ]
    }

    # 4. Open the modal
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://slack.com/api/views.open",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "trigger_id": trigger_id,
                "view": modal_view
            }
        )

    return {
        "response_action": "update",
        "view": {
            "type": "modal",
            "title": {"type": "plain_text", "text": "✅ Settings Saved"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🎉 Your settings were saved successfully!\nYou can update them anytime with `/settings`."
                    }
                }
            ]
        }
    }
