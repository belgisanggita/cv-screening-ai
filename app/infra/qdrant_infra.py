from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from fastembed import TextEmbedding

from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@lru_cache
def get_qdrant_client() -> QdrantClient:
    logger.info(f"Connecting to Qdrant at {settings.QDRANT_URL}")
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


@lru_cache
def get_embedder() -> TextEmbedding:
    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    return TextEmbedding(model_name=settings.EMBEDDING_MODEL)


def embed_text(text: str) -> list[float]:
    embedder = get_embedder()
    embedding = list(embedder.embed([text]))[0]
    return embedding.tolist()


def ensure_collection() -> None:
    client = get_qdrant_client()
    collection_name = settings.QDRANT_COLLECTION_NAME

    if client.collection_exists(collection_name):
        logger.info(f"Collection '{collection_name}' already exists")
        return

    # Determine vector size from the embedder itself
    sample_vector = embed_text("dimension probe")
    vector_size = len(sample_vector)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(
            size=vector_size,
            distance=qmodels.Distance.COSINE,
        ),
    )
    logger.info(f"Created collection '{collection_name}' (dim={vector_size})")


def upsert_candidate(candidate_id: str, vector: list[float], payload: dict) -> None:
    client = get_qdrant_client()
    client.upsert(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points=[
            qmodels.PointStruct(
                id=candidate_id,
                vector=vector,
                payload=payload,
            )
        ],
    )
    logger.info(f"Upserted candidate {candidate_id} into Qdrant")


def delete_candidate(candidate_id: str) -> None:
    client = get_qdrant_client()
    client.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=qmodels.PointIdsList(points=[candidate_id]),
    )
    logger.info(f"Deleted candidate {candidate_id} from Qdrant")


def search_candidates(
    query_vector: list[float],
    limit: int = 10,
):
    client = get_qdrant_client()

    results = client.query_points(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    )
    return results.points