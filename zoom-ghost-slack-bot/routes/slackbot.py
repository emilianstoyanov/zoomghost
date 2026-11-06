# routes/slackbot.py
import os
import httpx
import requests
from fastapi import APIRouter, Request, HTTPException
from starlette.responses import RedirectResponse
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Missing Supabase credentials!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI")
FRONTEND_URL = (os.getenv("FRONTEND_URL") or "").rstrip("/")


def frontend_redirect(query: str) -> RedirectResponse:
    if not FRONTEND_URL:
        raise RuntimeError("Missing required env var: FRONTEND_URL")
    return RedirectResponse(f"{FRONTEND_URL}?{query}")


@router.get("/install")
async def install(request: Request):
    uid = request.query_params.get("uid")
    if not uid:
        raise HTTPException(status_code=400, detail="Missing uid (Supabase user ID)")

    slack_oauth_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&scope=commands,chat:write,users:read,files:write"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={uid}"
    )

    return RedirectResponse(slack_oauth_url)


@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    user_id = request.query_params.get("state")

    if not code or not user_id:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("https://slack.com/api/oauth.v2.access", data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI,
            })

        data = response.json()
        if not data.get("ok"):
            return frontend_redirect("slack=error")

        slack_user_id = data["authed_user"]["id"]
        slack_access_token = data["access_token"]
        team_id = data["team"]["id"]
        team_name = data["team"]["name"]
        expires_in = data.get("expires_in", 3600)

        user_info = requests.get(
            "https://slack.com/api/users.info",
            headers={"Authorization": f"Bearer {slack_access_token}"},
            params={"user": [slack_user_id]}
        ).json()
        slack_username = user_info.get("user", {}).get("name")

        email_result = supabase.table("users").select("email").eq("id", user_id).single().execute()
        user_email = email_result.data.get("email") if email_result.data else None

        if not user_email:
            raise HTTPException(status_code=400, detail="No email was found for this user.")

        existing_tokens = supabase.table("oauth_tokens").select("id").eq("provider", "slack") \
            .eq("provider_user_id", slack_user_id).neq("user_id", user_id).execute()
        if existing_tokens.data:
            return frontend_redirect("slack=exists")

        supabase.table("users").upsert({"id": user_id, "email": user_email}).execute()

        supabase.table("oauth_tokens").update({
            "is_active": False
        }).eq("user_id", user_id).eq("provider", "slack").execute()

        supabase.table("oauth_tokens").insert({
            "user_id": user_id,
            "provider": "slack",
            "provider_user_id": slack_user_id,
            "access_token": slack_access_token,
            "refresh_token": data.get("refresh_token"),
            "expires_at": (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat(),
            "is_active": True,
            "metadata": {
                "team_id": team_id,
                "team_name": team_name,
                "username": slack_username
            }
        }).execute()

        return frontend_redirect("slack=connected")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"detail": "Slack OAuth error", "error": str(e)}
