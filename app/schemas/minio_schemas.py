from pydantic import BaseModel, Field


class MinioFileSchema(BaseModel):
    bucket_name: str = Field(..., description="Nama bucket MinIO tempat file disimpan")
    object_name: str = Field(..., description="Path object di MinIO, contoh: candidate_xyz.pdf")