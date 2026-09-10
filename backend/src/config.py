import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)

LLM_SERVER_URL = os.getenv("LLM_SERVER_URL")
WHISPER_SERVER_URL = os.getenv("WHISPER_SERVER_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
WHISPER_API_KEY = os.getenv("WHISPER_API_KEY", "not-needed")
DEFAULT_MODEL_ID = os.getenv("DEFAULT_MODEL_ID", "qwen3.5-custom:latest")
LLM_SERVER_URL_MODELS = os.getenv("LLM_SERVER_URL_MODELS")
WHISPER_SERVER_URL_MODELS = os.getenv("WHISPER_SERVER_URL_MODELS")
