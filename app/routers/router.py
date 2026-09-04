from fastapi import APIRouter

from app.routers.ingest import router as ingest_router
from app.routers.chat import router as chat_router

router = APIRouter()
router.include_router(ingest_router, tags=["RAG"])
router.include_router(chat_router, tags=["Chat"])