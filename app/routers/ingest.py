from fastapi import APIRouter

from app.controllers.ingest_controller import handle_ingest_cv
from app.schemas.rag_schemas import IngestRequest, IngestResponse

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_cv(request: IngestRequest):
    return await handle_ingest_cv(request)