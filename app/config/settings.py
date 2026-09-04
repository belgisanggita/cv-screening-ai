import os
from dotenv import load_dotenv

# Get the directory of the current file
current_dir = os.path.dirname(os.path.abspath(__file__))
# Navigate up to the project root and then to the config directory
env_path = os.path.join(current_dir, "..", "..", "config", "properties.env")

# Load environment variables from the .env file
load_dotenv(dotenv_path=env_path)

# App
APP_NAME = os.getenv("APP_NAME", "CV Screening AI")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_PORT = int(os.getenv("APP_PORT", 8000))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
API_PREFIX = os.getenv("API_PREFIX", "/api/v1")

# LLM (OpenRouter, OpenAI-compatible)
OPENROUTER_API_KEY = os.getenv("open_router.api_key")
OPENROUTER_BASE_URL = os.getenv("open_router.url", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("open_router.model")

#Embedding
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "candidates")

# MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "cv-files")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"