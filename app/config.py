import os

DREMIO_HOST = os.getenv("DREMIO_HOST", "dremio")
DREMIO_REST_PORT = int(os.getenv("DREMIO_REST_PORT", "9047"))
DREMIO_USER = os.getenv("DREMIO_USER", "admin")
DREMIO_PASSWORD = os.getenv("DREMIO_PASSWORD", "admin123")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_CHAT_MODEL = os.getenv("NVIDIA_CHAT_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_EMBEDDING_MODEL = os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/nv-embed-qa-4")

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "egypt_investment_gold")
CHROMA_URL = os.getenv("CHROMA_URL", f"http://{CHROMA_HOST}:{CHROMA_PORT}")

RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", "0.0"))
