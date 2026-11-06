# routes/recordings_api.py
import os
from fastapi import Request
import requests
import logging
from dotenv import load_dotenv
from supabase import create_client
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
logger = logging.getLogger("zoomghost.recordings")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY or not JWT_SECRET:
    raise RuntimeError("Missing Supabase config environment variables")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

security = HTTPBearer()


def get_user_id_from_token(token: str) -> str:
    # Try to read the user from the token through the Supabase API
    try:
        # Standard approach through the Supabase API
        res = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": SUPABASE_SERVICE_ROLE_KEY
            }
        )
        if res.status_code == 200:
            user_data = res.json()
            user_id = user_data.get("id")
            if user_id:
                return user_id

        logger.warning(f"Supabase API response: {res.status_code}, {res.text}")
    except Exception as e:
        logger.warning(f"Failed to get user_id from token via API: {e}")

    # Try to decode the JWT locally
    try:
        import jwt
        decoded = jwt.decode(token, options={"verify_signature": False})
        logger.info(f"JWT decoded: {decoded}")

        # Supabase tokens store the user id in the sub field
        if "sub" in decoded:
            return decoded["sub"]

        # Otherwise, look at the other fields
        if "user_id" in decoded:
            return decoded["user_id"]
    except Exception as e:
        logger.warning(f"Failed to decode token locally: {e}")

    # If every attempt fails, return an error
    raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/recordings")
async def get_user_recordings(request: Request, user_id: str = None,
                              credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    # Debug log
    logger.info(f"Headers: {request.headers}")
    logger.info(f"Query params: {request.query_params}")

    # If user_id is present as a query parameter, use it instead of parsing the token
    if user_id:
        logger.info(f"Using user_id from query parameter: {user_id}")
    else:
        # Previous logic that reads the user from the token
        try:
            user_id = get_user_id_from_token(token)
            logger.info(f"Extracted user_id from token: {user_id}")
        except Exception as e:
            logger.error(f"Failed to get user_id from token: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid token")

    # Load the recordings from Supabase
    try:
        result = (
            supabase
            .from_("zoom_recordings")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        logger.info(f"Found {len(result.data or [])} recordings for user {user_id}")
        return {"recordings": result.data or []}
    except Exception as e:
        logger.error(f"Supabase query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
