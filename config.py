import os
from dotenv import load_dotenv
from supabase import create_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
USERS_FILE = os.path.join(BASE_DIR, "users.json")
REQUESTS_FILE = os.path.join(BASE_DIR, "citizen_requests.csv")

load_dotenv(os.path.join(BASE_DIR, ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Supabase environment variables are missing. Check the .env file."
    )

# SUPABASE_URL must be the project URL, e.g. https://PROJECT_ID.supabase.co
# Do not append /rest/v1 to this URL.
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
