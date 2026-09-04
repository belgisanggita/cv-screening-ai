from typing import Optional

from fastapi import Form, File, UploadFile
from pydantic import BaseModel, ConfigDict

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


class ChatFormRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: str
    client_id: str
    job_posting_id: str
    top_k: int = 5
    requirements_text: Optional[str] = None
    requirements_file: Optional[UploadFile] = None

    @classmethod
    def as_form(
        cls,
        message: str = Form(...),
        client_id: str = Form(...),
        job_posting_id: str = Form(...),
        top_k: int = Form(5),
        requirements_text: Optional[str] = Form(None),
        requirements_file: Optional[UploadFile] = File(None),
    ) -> "ChatFormRequest":
        return cls(
            message=message,
            client_id=client_id,
            job_posting_id=job_posting_id,
            top_k=top_k,
            requirements_text=requirements_text,
            requirements_file=requirements_file,
        )


class CandidateResult(BaseModel):
    document_id: str
    title: str
    score: float  # sekarang: match_score dari LLM (0-100), bukan cosine similarity
    minio_file: str
    file_url: Optional[str] = None
    reasoning: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    candidates: list[CandidateResult] = []