from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.summarize import router as summarize_router
from app.api.routes.zoom_webhook import router as zoom_webhook_router
from app.api.routes.slack_interactions import router as slack_interactions_router  # 🆕 Added here

router = APIRouter()

router.include_router(health_router, tags=["health"])
router.include_router(summarize_router, tags=["summarize"])
router.include_router(zoom_webhook_router, prefix="/zoom", tags=["Zoom Webhooks"])
router.include_router(slack_interactions_router, prefix="/slack", tags=["Slack Interactions"])  # 🆕 Added here
