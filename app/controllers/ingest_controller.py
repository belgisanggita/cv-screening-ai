import os

from fastapi import HTTPException

from app.infra.minio_infra import stat_object, get_object_bytes
from app.index.qdrant_index import ingest_document
from app.schemas.rag_schemas import IngestRequest, IngestResponse
from app.utils.pdf_extractor import extract_text_from_pdf
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def handle_ingest_cv(request: IngestRequest) -> IngestResponse:
    object_name = request.file.object_name

    if not stat_object(object_name):
        raise HTTPException(
            status_code=404,
            detail=f"File '{object_name}' not found in bucket '{request.file.bucket_name}'",
        )

    try:
        file_bytes = get_object_bytes(object_name)
    except Exception as e:
        logger.error(f"Failed to fetch file from MinIO: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch file from storage")

    try:
        extracted_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Ambil nama file dari path, contoh: "client_abc/job_123/Bayu.pdf" -> "Bayu.pdf"
    title = os.path.basename(object_name)

    try:
        result = ingest_document(
            request=request,
            title=title,
            extracted_text=extracted_text,
        )
    except Exception as e:
        logger.error(f"Failed to ingest document into Qdrant: {e}")
        raise HTTPException(status_code=500, detail="Failed to index document")

    return result