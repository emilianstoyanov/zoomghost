# main.py
import sys
import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv  # ✅ new

# Routers
from routes import zoom_webhook
from routes import slack_webhook
from routes.slackbot import router as slack_router
from routes.zoombot import router as zoom_router
from routes.recordings_api import router as recordings_router
from routes.slack_commands import router as slack_commands_router
from routes.slack_interactions import router as slack_interactions_router

# Logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("zoomghost")

# Load .env
load_dotenv()

# Create the app
app = FastAPI(title="ZoomGhost Bot")

# Determine the environment
APP_ENV = os.getenv("APP_ENV", "development")
logger.info("🟢 Application started successfully. Environment: %s", APP_ENV)

# CORS_ORIGINS overrides the defaults. Comma-separated, no spaces required.
raw_origins = os.getenv("CORS_ORIGINS")
if raw_origins:
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
elif APP_ENV == "production":
    origins = [
        "https://zoomghost.com",
        "https://www.zoomghost.com",
    ]
else:
    origins = [
        "http://localhost:3000",
    ]

# ✅ CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"👉 Request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"✅ Response: {response.status_code} for {request.url.path}")
        return response
    except Exception as e:
        logger.exception(f"❌ Error handling request to {request.url.path}")
        raise


# ROUTERS
app.include_router(slack_router, prefix="/api/slack")
app.include_router(slack_commands_router, prefix="/api/slack")
app.include_router(slack_interactions_router, prefix="/api/slack")
app.include_router(slack_webhook.router, prefix="/api/slack")
app.include_router(zoom_router, prefix="/api/zoom")
app.include_router(zoom_webhook.router, prefix="/api/zoom")
app.include_router(recordings_router, prefix="/api")


@app.get("/")
def home():
    return {"message": "ZoomGhost Bot is alive 🚀"}


@app.post("/api/slack/hello")
async def handle_hello(request: Request):
    data = await request.form()
    user_id = data.get("user_id")
    return {"text": f"👋 Hello <@{user_id}>! I'm alive!"}
