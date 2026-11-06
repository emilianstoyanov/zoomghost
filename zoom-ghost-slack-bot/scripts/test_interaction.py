from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def test_lookup(meeting_id: str):
    print(f"🔍 Looking up the recording for zoom_meeting_id = {meeting_id}")
    try:
        rec_res = supabase.table("zoom_recordings") \
            .select("*") \
            .eq("zoom_meeting_id", meeting_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .maybe_single() \
            .execute()

        if not rec_res.data:
            print("❌ No recording with that meeting_id")
            return

        print("✅ Recording found:")
        print(rec_res.data)

    except Exception as e:
        print(f"❌ Exception: {str(e)}")


if __name__ == "__main__":
    meeting_id = os.getenv("ZOOM_MEETING_ID")
    if not meeting_id:
        raise SystemExit("Set ZOOM_MEETING_ID.")
    test_lookup(meeting_id)
