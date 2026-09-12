"""Точка входа backend-сервиса auto-summary (FastAPI).

Пайплайн обработки встречи/лекции:
    Upload (видео/аудио) -> FFmpeg (WAV 16 kHz mono) -> Whisper (STT, ru)
    -> Ollama (LLM, саммари в Markdown) -> сохранение .md на диск.

Ручки:
    POST /api/v1/meeting/process — полный пайплайн обработки файла.
    POST /api/v1/models/import   — импорт .gguf-модели в Ollama из /models.
    GET  /health                 — проверка доступности Whisper и Ollama.
"""

import asyncio
import functools
import time
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.responses import JSONResponse
from ollama import AsyncClient
from openai import AsyncOpenAI

from src.audio import extract_audio_from_video
from src.config import (
    LLM_API_KEY,
    LLM_SERVER_URL,
    LLM_SERVER_URL_MODELS,
    WHISPER_SERVER_URL_MODELS,
    OLLAMA_SERVER_URL,
    logger
)
from src.llm import generate_summary
from src.shemas.models import CreateModelRequest
from src.stt import transcribe_audio

# FastAPI-приложение. Версия дублируется в CHANGELOG.md
app = FastAPI(title="auto-summary", version="0.2.0")

# Клиент OpenAI-совместимого API Ollama: используется для chat-запросов (саммари).
ai_client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_SERVER_URL)

# Нативный клиент Ollama: используется для административных операций
# (импорт моделей через create/blob). Требует "чистый" host без суффикса /v1,
# поэтому берётся из OLLAMA_SERVER_URL, а не из LLM_SERVER_URL.
ollama_client = AsyncClient(host=OLLAMA_SERVER_URL)

# Локальное файловое хранилище (в Docker смонтировано как ./backend/storage -> /app/storage):
# uploads — исходные загруженные файлы, audio — извлечённый WAV, summaries — итоговые .md.
BASE_DIR = Path("storage")
UPLOAD_DIR = BASE_DIR / "uploads"
AUDIO_DIR = BASE_DIR / "audio"
SUMMARY_DIR = BASE_DIR / "summaries"

# Создаем папки, если их еще нет
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

# Директория с .gguf-файлами для импорта моделей в Ollama.
# Смонтирована как ./models -> /models в сервисах backend и llm-server (см. docker-compose.yml).
MODEL_DIR = Path("/models")


def time_it(func):
    """Декоратор: замеряет время выполнения async-ручки и пишет его в лог."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()

        try:
            return await func(*args, **kwargs)
        finally:
            execution_time = time.perf_counter() - start_time
            logger.info(
                "Время выполнения %s: %.2f сек.",
                func.__name__,
                execution_time,
            )

    return wrapper


@app.post("/api/v1/meeting/process", status_code=status.HTTP_200_OK)
@time_it
async def process_meeting(
        file: UploadFile = File(...),
        model_id: str = "qwen3.5-custom:latest",
):
    """Полный пайплайн: сохранение файла -> FFmpeg -> Whisper -> LLM -> .md на диск.

    Args:
        file: загружаемый аудио/видеофайл (любой формат, понятный FFmpeg).
        model_id: имя модели Ollama для генерации саммари.

    Returns:
        JSON с task_id, статусом, именем .md-файла, текстом саммари и транскриптом.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Файл не был загружен."
        )

    file_name = Path(file.filename).stem
    file_extension = Path(file.filename).suffix

    saved_video_path = UPLOAD_DIR / f"{file_name}{file_extension}"
    extracted_audio_path = AUDIO_DIR / f"{file_name}.wav"
    summary_md_path = SUMMARY_DIR / f"{file_name} summary.md"

    # Сохранение загруженного медиафайла
    try:
        logger.info("Сохранение загруженного медиафайла")
        with open(saved_video_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при сохранении файла: {str(e)}",
        )
    finally:
        await file.close()

    # Извлечение аудио через FFmpeg
    try:
        await asyncio.to_thread(
            extract_audio_from_video,
            input_path=saved_video_path,
            output_path=extracted_audio_path,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось извлечь аудиодорожку: {str(e)}",
        )

    # Транскрибация через Whisper
    try:
        logger.info("Транскрибация через Whisper")
        raw_transcript = await transcribe_audio(extracted_audio_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось транскрибировать аудио: {str(e)}",
        )

    # Генерация резюме через LLM server
    try:
        logger.info("Генерация резюме через LLM server")
        summary_markdown = await generate_summary(
            transcript=raw_transcript, model_id=model_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось сгенерировать резюме: {str(e)}",
        )

    # Сохранение итогового .md файла на диск
    try:
        logger.info("Сохранение итогового .md файла на диск")
        with open(summary_md_path, "w", encoding="utf-8") as f:
            f.write(summary_markdown)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось сохранить Markdown файл: {str(e)}",
        )

    # Ответ
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "task_id": file_name,
            "status": "COMPLETED",
            "original_filename": file.filename,
            "summary_file": str(summary_md_path.name),
            "summary_markdown": summary_markdown,
            "raw_transcript": raw_transcript,
        },
    )


@app.post("/api/v1/models/import")
async def create_custom_model(payload: CreateModelRequest):
    """Импорт .gguf-модели из директории /models в Ollama.

    Шаги: проверка наличия .gguf-файла -> загрузка блоба в Ollama
    (create_blob возвращает digest) -> создание модели (create) с параметрами
    temperature/num_ctx из тела запроса.

    Args:
        payload: имя новой модели, имя .gguf-файла и параметры генерации.

    Returns:
        JSON с сообщением, digest загруженного блоба и ответом Ollama.
    """
    try:
        # Имя файла из запроса ищем строго внутри /models (без поддиректорий).
        gguf_path = MODEL_DIR / payload.gguf_file

        if not gguf_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GGUF-файл '{payload.gguf_file}' не найден",
            )

        # Шаг 1: заливаем .gguf в Ollama как blob, получаем его digest.
        digest = await ollama_client.create_blob(gguf_path)

        # Шаг 2: создаём модель, ссылаясь на blob по digest.
        # parameters — опции инференса (температура, размер контекста).
        response = await ollama_client.create(
            model=payload.model_name,
            files={
                gguf_path.name: digest,
            },
            parameters={
                "temperature": payload.temperature,
                "num_ctx": payload.num_ctx,
            },
        )

        return {
            "message": f"Модель '{payload.model_name}' создана",
            "digest": digest,
            "ollama_response": response,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка Ollama: {e}",
        )


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(response: Response):
    """Проверка доступности зависимостей (Whisper и Ollama).

    Опрашивает /models обоих сервисов с таймаутом 3 c. Если хотя бы одна
    зависимость не healthy — возвращает статус degraded и HTTP 503.
    """
    health_status = {
        "status": "ok",
        "dependencies": {"whisper": "unknown", "ollama": "unknown"},
    }

    async with httpx.AsyncClient(timeout=3.0) as client:
        # Проверка Whisper
        try:
            res_whisper = await client.get(WHISPER_SERVER_URL_MODELS)
            health_status["dependencies"]["whisper"] = (
                "healthy" if res_whisper.status_code == 200 else "unhealthy"
            )
        except Exception:
            health_status["dependencies"]["whisper"] = "unreachable"

        # Проверка Ollama
        try:
            res_ollama = await client.get(LLM_SERVER_URL_MODELS)
            health_status["dependencies"]["ollama"] = (
                "healthy" if res_ollama.status_code == 200 else "unhealthy"
            )
        except Exception:
            health_status["dependencies"]["ollama"] = "unreachable"

    # Если хотя бы один зависимый сервис недоступен — меняем статускод на 503.
    # Внимание: здесь сравнивается значение из словаря, а не модуль fastapi.status.
    if any(dep_status != "healthy" for dep_status in health_status["dependencies"].values()):
        health_status["status"] = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return health_status


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, timeout_keep_alive=0, host="0.0.0.0", port=8080)
