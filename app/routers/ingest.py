from fastapi import APIRouter

from app.controllers.ingest_controller import handle_ingest_cv, handle_delete_cv
from app.schemas.rag_schemas import IngestRequest, IngestResponse, DeleteResponse

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_cv(request: IngestRequest):
    return await handle_ingest_cv(request)


@router.delete("/delete/{document_id}", response_model=DeleteResponse)
async def delete_cv(document_id: str):
    return await handle_delete_cv(document_id)