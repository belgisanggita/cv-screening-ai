from typing import Optional

from fastapi import HTTPException, UploadFile

from app.infra.minio_infra import get_presigned_url
from app.index.qdrant_index import search_documents
from app.llm.openai_llm import get_llm
from app.prompts.chat_prompt import (
    CHAT_SYSTEM_PROMPT,
    build_requirements_section,
    build_candidates_section,
)
from app.schemas.rag_schemas import ChatResponse, CandidateResult
from app.utils.pdf_extractor import extract_text_from_pdf
from app.utils.logger import setup_logger

import asyncio

logger = setup_logger(__name__)


async def resolve_doc_requirements(
    requirements_text: Optional[str],
    requirements_file: Optional[UploadFile],
) -> Optional[str]:
    """Ambil requirements dari text langsung, atau extract dari file PDF (di memory, tidak disimpan)."""
    if requirements_text:
        return requirements_text

    if requirements_file:
        file_bytes = await requirements_file.read()
        # Jalankan extract di thread terpisah biar gak block event loop
        return await asyncio.to_thread(extract_text_from_pdf, file_bytes)

    return None


def build_candidate_result(c) -> CandidateResult:
    """Susun hasil kandidat + generate presigned URL buat akses file CV di MinIO."""
    bucket_name, _, object_name = c.minio_file.partition("/")

    file_url = get_presigned_url(object_name, bucket_name=bucket_name, expires_minutes=60)

    return CandidateResult(
        document_id=c.document_id,
        title=c.title,
        score=c.score,
        minio_file=c.minio_file,
        file_url=file_url,
    )


async def handle_chat(
    message: str,
    client_id: str,
    job_posting_id: str,
    top_k: int,
    requirements_text: Optional[str] = None,
    requirements_file: Optional[UploadFile] = None,
) -> ChatResponse:
    # 1. Resolve requirements (text/file/none)
    doc_requirements = await resolve_doc_requirements(requirements_text, requirements_file)

    # 2. Query vector: gabungan message + requirements (kalau ada) buat retrieval yang lebih relevan
    query_text = message
    if doc_requirements:
        query_text = f"{message}\n{doc_requirements}"

    # 3. Retrieve kandidat relevan dari Qdrant
    candidates = search_documents(
        query_text=query_text,
        client_id=client_id,
        job_posting_id=job_posting_id,
        limit=top_k,
    )

    if not candidates:
        return ChatResponse(
            answer="Tidak ada kandidat ditemukan untuk job posting ini.",
            candidates=[],
        )

    # 4. Build prompt
    prompt = CHAT_SYSTEM_PROMPT.format(
        requirements_section=build_requirements_section(doc_requirements),
        message=message,
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

    # 6. Susun response, sekalian generate presigned URL per kandidat
    return ChatResponse(
        answer=response.content,
        candidates=[build_candidate_result(c) for c in candidates],
    )