from fastapi import APIRouter, HTTPException
from app.services.summarize_service import summarize_text

router = APIRouter()

@router.post("/summarize")
async def summarize(payload: dict):
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    return {"summary": summarize_text(text)}
