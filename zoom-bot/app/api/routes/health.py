from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.logging_config import setup_logger

router = APIRouter()

logger = setup_logger(__name__)


@router.get("/health")
async def health_router():
    return JSONResponse(content={"status": "ok"})
