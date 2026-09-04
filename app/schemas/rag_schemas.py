from typing import Optional
from pydantic import BaseModel, model_validator

from app.schemas.minio_schemas import MinioFileSchema


class IngestRequest(BaseModel):
    document_id: str
    file: MinioFileSchema
    client_id: str
    job_posting_id: str


class IngestResponse(BaseModel):
    document_id: str
    title: str
    client_id: str
    job_posting_id: str
    status: str
    minio_file: str

class ChatRequest(BaseModel):
    message: str
    requirements_text: Optional[str] = None
    requirements_file: Optional[MinioFileSchema] = None
    client_id: str
    job_posting_id: str
    top_k: int = 5

    @model_validator(mode="after")
    def check_requirements_not_both(self):
        if self.requirements_text and self.requirements_file:
            raise ValueError("Isi salah satu saja: requirements_text atau requirements_file, jangan dua-duanya")
        return self


class CandidateResult(BaseModel):
    document_id: str
    title: str
    score: float
    minio_file: str
    file_url: str | None = None


class ChatResponse(BaseModel):
    answer: str
    candidates: list[CandidateResult] = []