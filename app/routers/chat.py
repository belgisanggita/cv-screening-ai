from typing import Optional

from fastapi import APIRouter, Form, UploadFile, File

from app.controllers.chat_controller import handle_chat
from app.schemas.rag_schemas import ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    client_id: str = Form(...),
    job_posting_id: str = Form(...),
    top_k: int = Form(5),
    requirements_text: Optional[str] = Form(None),
    requirements_file: Optional[UploadFile] = File(None),
):
    return await handle_chat(
        message=message,
        client_id=client_id,
        job_posting_id=job_posting_id,
        top_k=top_k,
        requirements_text=requirements_text,
        requirements_file=requirements_file,
    )