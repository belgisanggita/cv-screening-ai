import uuid
from datetime import datetime, timezone

from app.infra.qdrant_infra import embed_text, upsert_candidate, search_candidates, delete_candidate
from app.schemas.qdrant_schemas import CandidatePayload, CandidateSearchResult
from app.schemas.rag_schemas import IngestRequest, IngestResponse
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def ingest_document(request: IngestRequest, title: str, extracted_text: str) -> IngestResponse:
    document_id = str(request.document_id)
    minio_file = f"{request.file.bucket_name}/{request.file.object_name}"

    payload = CandidatePayload(
        document_id=document_id,
        title=title,
        minio_file=minio_file,
        date=datetime.now(timezone.utc),
        text=extracted_text,
    )

    vector = embed_text(extracted_text)
    upsert_candidate(document_id, vector, payload.model_dump(mode="json"))

    logger.info(f"Ingested document {document_id}")

    return IngestResponse(
        document_id=document_id,
        title=title,
        status="success",
        minio_file=minio_file,
    )


def delete_document(document_id: str) -> None:
    delete_candidate(document_id)
    logger.info(f"Deleted document {document_id}")


def search_documents(
    query_text: str,
    limit: int = 10,
) -> list[CandidateSearchResult]:
    query_vector = embed_text(query_text)
    points = search_candidates(query_vector, limit)

    return [
        CandidateSearchResult(**point.payload, score=point.score)
        for point in points
    ]