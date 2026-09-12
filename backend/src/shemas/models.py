"""Pydantic-схемы запросов для ручек управления моделями Ollama."""

from pydantic import BaseModel, Field


class CreateModelRequest(BaseModel):
    """Тело запроса POST /api/v1/models/import: создать модель в Ollama из .gguf-файла."""

    # Имя, под которым модель появится в Ollama (видно в `ollama list`).
    model_name: str = Field(default="Qwen3.5-custom:latest")

    # Путь к .gguf-файлу. Резолвится относительно MODEL_DIR (/models в контейнере).
    gguf_file: str = Field()

    # Опции инференса, передаются в ollama.create(parameters={...}).
    # None означает "не передавать" (Ollama применит свои дефолты).
    temperature: float | None = Field(default=0.8)
    num_ctx: int | None = Field(default=24576)

    # Перезапись модели с тем же именем. False (по умолчанию) — ручка вернёт
    # 409, если модель уже существует; True — старая модель будет удалена
    # (в ответе вернётся "replaced": true).
    overwrite: bool = False
