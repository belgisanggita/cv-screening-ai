import asyncio
import json
from typing import Optional

from fastapi import HTTPException

from app.infra.minio_infra import get_presigned_url
from app.index.qdrant_index import search_documents
from app.llm.openai_llm import get_llm
from app.prompts.chat_prompt import (
    CHAT_SYSTEM_PROMPT,
    INTENT_CHECK_PROMPT,
    build_requirements_section,
    build_candidates_section,
)
from app.schemas.rag_schemas import ChatFormRequest, ChatResponse, CandidateResult
from app.utils.pdf_extractor import extract_text_from_pdf
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

FALLBACK_MESSAGE = (
    "Maaf, saya khusus membantu pencarian dan penyaringan kandidat berdasarkan CV. "
    "Coba tanyakan sesuatu terkait kandidat, misalnya: "
    "\"Carikan kandidat yang cocok untuk posisi Interior Designer\", "
    "atau lampirkan dokumen requirements posisi yang sedang dibuka."
)

MIN_RELEVANCE_SCORE = 0.5  # threshold vector similarity, sebelum LLM scoring dipanggil

NO_MATCH_MESSAGE_TEMPLATE = (
    "Tidak ada dokumen CV yang tersedia untuk posisi/kriteria \"{message}\" pada job posting ini. "
    "Kandidat yang ada di database untuk job posting ini memiliki latar belakang yang berbeda "
    "dari yang diminta."
)


class ChatController:
    async def is_candidate_related(self, message: str) -> bool:
        llm = get_llm(temperature=0.0)
        prompt = INTENT_CHECK_PROMPT.format(message=message)

        try:
            response = llm.invoke(prompt)
            answer = response.content.strip().upper()
            is_related = answer.startswith("YA")
            logger.info(f"Intent check for message='{message[:50]}...' -> {answer} (related={is_related})")
            return is_related
        except Exception as e:
            logger.warning(f"Intent check failed, defaulting to related=True: {e}")
            return True

    async def resolve_doc_requirements(self, request: ChatFormRequest) -> Optional[str]:
        if request.requirements_text:
            logger.info("Using requirements_text from request body")
            return request.requirements_text

        if request.requirements_file:
            logger.info(f"Extracting requirements from uploaded file: {request.requirements_file.filename}")
            file_bytes = await request.requirements_file.read()
            text = await asyncio.to_thread(extract_text_from_pdf, file_bytes)
            logger.info(f"Extracted {len(text)} chars from requirements file")
            return text

        logger.info("No requirements provided (text or file)")
        return None

    def build_prompt(self, request: ChatFormRequest, doc_requirements: Optional[str], candidates: list) -> str:
        return CHAT_SYSTEM_PROMPT.format(
            requirements_section=build_requirements_section(doc_requirements),
            message=request.message,
            candidates_section=build_candidates_section(
                [{"document_id": c.document_id, "title": c.title, "text": c.text} for c in candidates]
            ),
        )

    def parse_llm_ranking(self, raw_content: str) -> Optional[dict]:
        """Parse JSON output dari LLM. Return None kalau gagal parse (biar bisa fallback)."""
        cleaned = raw_content.strip()
        # Strip markdown code fence kalau LLM tetap membungkusnya walau udah diminta jangan
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json\n", "", 1).replace("json\r\n", "", 1)

        try:
            parsed = json.loads(cleaned)
            if "summary" not in parsed or "ranked_candidates" not in parsed:
                logger.warning(f"LLM JSON missing required keys: {list(parsed.keys())}")
                return None
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM output as JSON: {e}. Raw content: {raw_content[:300]}")
            return None

    def build_ranked_candidate_results(self, parsed: dict, candidates: list) -> list[CandidateResult]:
        """Reorder & enrich hasil sesuai ranking dari LLM, gabungin sama metadata asli (title, minio_file)."""
        candidates_by_id = {c.document_id: c for c in candidates}
        results = []

        for ranked in parsed.get("ranked_candidates", []):
            doc_id = ranked.get("document_id")
            original = candidates_by_id.get(doc_id)

            if not original:
                logger.warning(f"LLM returned unknown document_id '{doc_id}', skipping")
                continue

            bucket_name, _, object_name = original.minio_file.partition("/")
            file_url = get_presigned_url(object_name, bucket_name=bucket_name, expires_minutes=60)

            results.append(
                CandidateResult(
                    document_id=original.document_id,
                    title=original.title,
                    score=float(ranked.get("match_score", 0)),
                    minio_file=original.minio_file,
                    file_url=file_url,
                    reasoning=ranked.get("reasoning"),
                )
            )

        return results

    def build_fallback_candidate_results(self, candidates: list) -> list[CandidateResult]:
        """Dipakai kalau parsing JSON dari LLM gagal — fallback ke urutan vector similarity asli."""
        results = []
        for c in candidates:
            bucket_name, _, object_name = c.minio_file.partition("/")
            file_url = get_presigned_url(object_name, bucket_name=bucket_name, expires_minutes=60)
            results.append(
                CandidateResult(
                    document_id=c.document_id,
                    title=c.title,
                    score=c.score,
                    minio_file=c.minio_file,
                    file_url=file_url,
                    reasoning=None,
                )
            )
        return results

    async def handle_chat(self, request: ChatFormRequest) -> ChatResponse:
        logger.info(
            f"Chat request received: client_id={request.client_id}, "
            f"job_posting_id={request.job_posting_id}, top_k={request.top_k}, "
            f"message='{request.message[:80]}'"
        )

        if not await self.is_candidate_related(request.message):
            logger.info("Message deemed unrelated to candidate search, returning fallback")
            return ChatResponse(answer=FALLBACK_MESSAGE, candidates=[])

        doc_requirements = await self.resolve_doc_requirements(request)

        query_text = request.message
        if doc_requirements:
            query_text = f"{request.message}\n{doc_requirements}"

        candidates = search_documents(
            query_text=query_text,
            client_id=request.client_id,
            job_posting_id=request.job_posting_id,
            limit=request.top_k,
        )
        logger.info(f"Retrieved {len(candidates)} candidates from Qdrant")

        if not candidates:
            logger.info("No candidates found for this job_posting_id, returning early")
            return ChatResponse(
                answer="Tidak ada kandidat ditemukan untuk job posting ini.",
                candidates=[],
            )

        top_score = candidates[0].score
        logger.info(f"Top candidate vector score: {top_score:.3f}")

        if top_score < MIN_RELEVANCE_SCORE:
            logger.info(
                f"Top candidate score ({top_score:.3f}) below relevance threshold "
                f"({MIN_RELEVANCE_SCORE}), returning no-match without calling LLM"
            )
            return ChatResponse(
                answer=NO_MATCH_MESSAGE_TEMPLATE.format(message=request.message),
                candidates=[],
            )

        prompt = self.build_prompt(request, doc_requirements, candidates)
        logger.debug(f"Prompt length: {len(prompt)} chars")

        llm = get_llm()
        try:
            response = llm.invoke(prompt)
            logger.info("LLM scoring call succeeded")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate response from LLM")

        parsed = self.parse_llm_ranking(response.content)

        if parsed:
            logger.info(f"LLM ranking parsed successfully, {len(parsed.get('ranked_candidates', []))} candidates ranked")
            return ChatResponse(
                answer=parsed["summary"],
                candidates=self.build_ranked_candidate_results(parsed, candidates),
            )
        else:
            logger.warning("Falling back to raw LLM text + vector-similarity order due to JSON parse failure")
            return ChatResponse(
                answer=response.content,
                candidates=self.build_fallback_candidate_results(candidates),
            )


chat_controller = ChatController()