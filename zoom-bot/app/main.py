# app/main.py
import os
import asyncio
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from app.logging_config import setup_logger
from app.router import router as api_router
from app.services.token_refresher import token_refresher_loop
from app.services.zoom_token_service import generate_server_to_server_token

# Load .env
load_dotenv()

# Initialize the logging system
logger = setup_logger("zoom-bot-main")

logger.info("✅ Zoom Bot API is starting...")
logger.info("🔐 OPENAI_API_KEY exists: %s", bool(os.getenv("OPENAI_API_KEY")))
logger.info("🔑 ZOOM_S2S_CLIENT_ID exists: %s", bool(os.getenv("ZOOM_S2S_CLIENT_ID")))

# Create the FastAPI application
app = FastAPI(
    title="Zoom Bot API",
    docs_url="/api/docs",
    redoc_url=None
)


# 🔍 Middleware that logs every request (temporary, for debugging)
@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    logger.info("📥 %s %s", request.method, request.url.path)
    return await call_next(request)


# Routers
app.include_router(api_router, prefix="/api")


# Start a background task when the application starts
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting the background task that refreshes the Zoom token...")

    # ➕ Generate a token if one is missing
    token = generate_server_to_server_token()
    if token:
        logger.info("✅ Initial Zoom S2S token generated.")
    else:
        logger.error("❌ Failed to generate the initial Zoom S2S token.")

    asyncio.create_task(token_refresher_loop(interval_minutes=50))
