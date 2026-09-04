import os

from fastapi import HTTPException

from app.infra.minio_infra import stat_object, get_object_bytes
from app.infra.qdrant_infra import embed_text
from app.index.qdrant_index import search_documents
from app.llm.openai_llm import get_llm
from app.prompts.chat_prompt import (
    CHAT_SYSTEM_PROMPT,
    build_requirements_section,
    build_candidates_section,
)
from app.schemas.rag_schemas import ChatRequest, ChatResponse, CandidateResult
from app.utils.pdf_extractor import extract_text_from_pdf
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def resolve_doc_requirements(request: ChatRequest) -> str | None:
    """Ambil requirements dari text langsung, atau extract dari file PDF kalau ada."""
    if request.requirements_text:
        return request.requirements_text

    if request.requirements_file:
        object_name = request.requirements_file.object_name

        if not stat_object(object_name):
            raise HTTPException(
                status_code=404,
                detail=f"Requirements file '{object_name}' not found in bucket",
            )

        file_bytes = get_object_bytes(object_name)
        return extract_text_from_pdf(file_bytes)

    return None


async def handle_chat(request: ChatRequest) -> ChatResponse:
    # 1. Resolve requirements (text/file/none)
    doc_requirements = resolve_doc_requirements(request)

    # 2. Query vector: gabungan message + requirements (kalau ada) buat retrieval yang lebih relevan
    query_text = request.message
    if doc_requirements:
        query_text = f"{request.message}\n{doc_requirements}"

    # 3. Retrieve kandidat relevan dari Qdrant
    candidates = search_documents(
        query_text=query_text,
        client_id=request.client_id,
        job_posting_id=request.job_posting_id,
        limit=request.top_k,
    )

    if not candidates:
        return ChatResponse(
            answer="Tidak ada kandidat ditemukan untuk job posting ini.",
            candidates=[],
        )

    # 4. Build prompt
    prompt = CHAT_SYSTEM_PROMPT.format(
        requirements_section=build_requirements_section(doc_requirements),
        message=request.message,
        candidates_section=build_candidates_section(
            [{"title": c.title, "text": c.text} for c in candidates]
        ),
    )

    # 5. Panggil LLM
    llm = get_llm()
    try:
        response = llm.invoke(prompt)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate response from LLM")

    return ChatResponse(
        answer=response.content,
        candidates=[
            CandidateResult(
                document_id=c.document_id,
                title=c.title,
                score=c.score,
                minio_file=c.minio_file,
            )
            for c in candidates
        ],
    )