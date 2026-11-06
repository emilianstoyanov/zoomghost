# scripts/generate_token.py
import os
import sys

# Add the app path so the import works
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from app.services.zoom_token_service import (
    generate_server_to_server_token,
    ZOOM_S2S_CLIENT_ID,
    ZOOM_S2S_CLIENT_SECRET,
    ZOOM_ACCOUNT_ID
)

# Load the .env file from the root directory
env_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path=env_path)

# 🛡️ Validate the Supabase key
supabase_key = os.getenv("SUPABASE_KEY")
print("🔐 SUPABASE_KEY prefix =", repr(supabase_key[:10]) if supabase_key else "❌ Missing!")

if not all([ZOOM_S2S_CLIENT_ID, ZOOM_S2S_CLIENT_SECRET, ZOOM_ACCOUNT_ID]):
    print("❌ A required value is missing. Check the .env file.")
    sys.exit(1)

if not supabase_key:
    print("❌ SUPABASE_KEY is missing. Add it to .env.")
    sys.exit(1)

if not supabase_key.startswith("eyJ") and not supabase_key.startswith("sb"):
    print("⚠️ Warning: SUPABASE_KEY does not look valid. Make sure it is a service role key.")
    sys.exit(1)

# 🚀 Generate a token
print("🚀 Generating a token with generate_server_to_server_token() ...")

token = generate_server_to_server_token()
if token:
    print(f"✅ Token generated:\n{token}")
else:
    print("❌ Failed to generate token.")
