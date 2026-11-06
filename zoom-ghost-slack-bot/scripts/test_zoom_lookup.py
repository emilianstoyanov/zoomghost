import os
from dotenv import load_dotenv
from supabase import create_client

# Load the .env file
load_dotenv()

# Read the credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Initialize the client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# 👉 Put a real Zoom meeting id here
zoom_meeting_id = os.getenv("ZOOM_MEETING_ID")
if not zoom_meeting_id:
    raise SystemExit("Set ZOOM_MEETING_ID.")

print(f"🔍 Looking up the recording for zoom_meeting_id: {zoom_meeting_id}")

try:
    result = supabase.table("zoom_recordings") \
                    .select("download_url") \
                    .eq("zoom_meeting_id", zoom_meeting_id) \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .maybe_single() \
                    .execute()

    if result.data:
        print("✅ Recording found:")
        for row in result.data:
            print(row)
    else:
        print("❌ No recording found for this Zoom meeting id.")

except Exception as e:
    print(f"❌ Error querying Supabase: {e}")
