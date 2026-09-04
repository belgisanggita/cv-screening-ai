from fastapi import APIRouter, Depends

from app.controllers.chat_controller import chat_controller
from app.schemas.rag_schemas import ChatFormRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatFormRequest = Depends(ChatFormRequest.as_form)):
    return await chat_controller.handle_chat(request)