from fastapi import APIRouter

from app.controllers.chat_controller import handle_chat
from app.schemas.rag_schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await handle_chat(request)