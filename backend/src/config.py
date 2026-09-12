"""Конфигурация backend-сервиса: чтение переменных окружения и общий логгер.

Источники значений (по приоритету):
    1. `environment` сервиса backend в docker-compose.yml (имена сервисов внутри сети).
    2. `backend/.env` (через `env_file`, шаблон — `backend/.env.example`).
    3. Дефолты, указанные ниже (для локального запуска без Docker).
"""

import logging
import os

# Базовый логгер сервиса: формат "дата [уровень] сообщение", уровень INFO.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)

# Base URL OpenAI-совместимых API (с суффиксом /v1): используются openai-клиентами.
LLM_SERVER_URL = os.getenv("LLM_SERVER_URL")
WHISPER_SERVER_URL = os.getenv("WHISPER_SERVER_URL")

# API-ключи — формальность для локальных серверов, но параметр обязателен для клиентов.
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
WHISPER_API_KEY = os.getenv("WHISPER_API_KEY", "not-needed")

# Модель LLM по умолчанию (пока используется только как ориентир — ручка
# /api/v1/meeting/process берёт model_id из параметра запроса).
DEFAULT_MODEL_ID = os.getenv("DEFAULT_MODEL_ID", "qwen3.5-custom:latest")

# URL списков моделей — для проверки зависимостей в GET /health.
LLM_SERVER_URL_MODELS = os.getenv("LLM_SERVER_URL_MODELS")
WHISPER_SERVER_URL_MODELS = os.getenv("WHISPER_SERVER_URL_MODELS")

# "Чистый" host нативного API Ollama (без /v1) — для ollama.AsyncClient
# (административные операции: create/blob). Дефолт — имя сервиса в compose-сети.
OLLAMA_SERVER_URL = os.getenv("OLLAMA_SERVER_URL", "http://llm-server:11434")
