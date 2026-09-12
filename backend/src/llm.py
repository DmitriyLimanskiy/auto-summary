"""Клиент LLM: генерация Markdown-конспекта из транскрипта через Ollama."""

from pathlib import Path

from openai import AsyncOpenAI, OpenAIError

from .config import LLM_API_KEY, LLM_SERVER_URL

# Клиент поверх OpenAI-совместимого API Ollama (/v1): используется для chat-запросов.
ai_client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_SERVER_URL)

# Системный промпт конспекта лекции. Загружается один раз при старте модуля.
SYSTEM_PROMPT = Path("src/prompts/sys_prompt_2.txt").read_text(encoding="utf-8")


async def generate_summary(transcript: str, model_id: str) -> str:
    """
    Отправляет транскрипт в Ollama (OpenAI-совместимый API)
    и возвращает сгенерированный Markdown-конспект.

    Args:
        transcript: полный текст транскрипции встречи/лекции.
        model_id: имя модели в Ollama (например, "qwen3.5-custom:latest").

    Returns:
        Markdown-текст конспекта (первый вариант ответа модели).

    Raises:
        RuntimeError: если LLM-сервер вернул ошибку.
    """
    try:
        response = await ai_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Вот транскрипт встречи:\n\n{transcript}"},
            ],
            temperature=0.2,  # Низкая температура — меньше выдумок, строже по тексту
        )
        return response.choices[0].message.content
    except OpenAIError as e:
        raise RuntimeError(f"Ошибка при обращении к LLM SERVER: {str(e)}")
