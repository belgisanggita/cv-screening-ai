from datetime import datetime
from pydantic import BaseModel


class CandidatePayload(BaseModel):
    document_id: str
    title: str
    minio_file: str
    date: datetime
    text: str


class CandidateSearchResult(CandidatePayload):
    score: float