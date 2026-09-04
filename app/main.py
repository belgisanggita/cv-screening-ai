import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routers.router import router
from app.utils.logger import setup_logger
from app.config import settings
from app.infra.qdrant_infra import ensure_collection
from app.infra.minio_infra import ensure_bucket

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")

    logger.info("Ensuring Qdrant collection exists...")
    ensure_collection()

    logger.info("Ensuring MinIO bucket exists...")
    ensure_bucket()

    yield
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI-assisted CV screening service using RAG (Qdrant) + LLM",
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    app.include_router(router, prefix=settings.API_PREFIX)

    return app


app = create_app()


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )