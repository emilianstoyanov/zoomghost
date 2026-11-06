import os
import httpx
from fastapi import APIRouter, Request, HTTPException
from starlette.responses import RedirectResponse, HTMLResponse
from dotenv import load_dotenv
from datetime import datetime, timedelta
from supabase import create_client, Client

load_dotenv()
router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_REDIRECT_URI = os.getenv("ZOOM_REDIRECT_URI")
FRONTEND_URL = (os.getenv("FRONTEND_URL") or "").rstrip("/")


def frontend_redirect(query: str) -> RedirectResponse:
    if not FRONTEND_URL:
        raise RuntimeError("Missing required env var: FRONTEND_URL")
    return RedirectResponse(f"{FRONTEND_URL}?{query}")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Missing Supabase credentials!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


@router.get("/install")
async def zoom_install(request: Request):
    uid = request.query_params.get("uid")
    if not uid:
        raise HTTPException(status_code=400, detail="Missing uid")

    zoom_oauth_url = (
        f"https://zoom.us/oauth/authorize"
        f"?response_type=code"
        f"&client_id={ZOOM_CLIENT_ID}"
        f"&redirect_uri={ZOOM_REDIRECT_URI}"
        f"&state={uid}"
    )
    return RedirectResponse(zoom_oauth_url)


@router.get("/oauth/callback")
async def zoom_callback(request: Request):
    code = request.query_params.get("code")
    user_id = request.query_params.get("state")

    if not code or not user_id:
        # Friendlier page when someone opens the URL directly
        html_content = """
        <html><body>
        <h3 style="color:red;">❌ Missing Zoom OAuth parameters.</h3>
        <p>You should start the authorization process from <code>/install?uid=...</code>.</p>
        </body></html>
        """
        return HTMLResponse(content=html_content, status_code=400)

    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://zoom.us/oauth/token",
                params={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": ZOOM_REDIRECT_URI
                },
                auth=(ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET),
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            token_data = token_res.json()

            if "access_token" not in token_data:
                print("❌ Token exchange failed:", token_data)
                return frontend_redirect("zoom=error")

            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            user_info_res = await client.get(
                "https://api.zoom.us/v2/users/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_info = user_info_res.json()

            if user_info_res.status_code != 200:
                raise Exception(f"❌ Could not fetch Zoom user info: {user_info}")

            print("📦 Zoom user info raw:", user_info)

        zoom_id = user_info.get("id") or "unknown"
        email = user_info.get("email") or None
        first_name = user_info.get("first_name", "")
        last_name = user_info.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip()

        # Deactivate the old rows
        supabase.table("oauth_tokens").update({"is_active": False}) \
            .eq("user_id", user_id).eq("provider", "zoom").execute()

        # Store the new tokens
        supabase.table("oauth_tokens").insert({
            "user_id": user_id,
            "provider": "zoom",
            "provider_user_id": zoom_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat(),
            "is_active": True,
            "metadata": {
                "email": email,
                "full_name": full_name
            }
        }).execute()

        return frontend_redirect("zoom=connected")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "detail": "Zoom OAuth error",
            "error": str(e)
        }
