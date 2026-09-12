"""Клиент Speech-to-Text: транскрибация аудио через faster-whisper-server."""

from pathlib import Path

from openai import AsyncOpenAI, OpenAIError

from .config import WHISPER_API_KEY, WHISPER_SERVER_URL

# Создаем клиент AsyncOpenAI поверх OpenAI-совместимого API Whisper-сервера.
whisper_client = AsyncOpenAI(api_key=WHISPER_API_KEY, base_url=WHISPER_SERVER_URL)


async def transcribe_audio(audio_path: Path) -> str:
    """
    Отправляет сохраненный .wav файл в локальный контейнер Whisper
    и возвращает итоговый расшифрованный текст.

    Args:
        audio_path: путь к .wav-файлу (16 kHz mono, готовит audio.extract_audio_from_video).

    Returns:
        Полный текст транскрипции на русском языке.

    Raises:
        FileNotFoundError: если файла нет на диске.
        RuntimeError: если Whisper-сервер вернул ошибку.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Файл не найден по пути: {audio_path}")

    try:
        with open(audio_path, "rb") as audio_file:
            transcript = await whisper_client.audio.transcriptions.create(
                model="whisper-1",  # Имя модели фиксировано для совместимости со спецификацией OpenAI
                file=audio_file,
                language="ru",  # Сервис заточен под русскоязычные встречи/лекции
            )
        return transcript.text
    except OpenAIError as e:
        raise RuntimeError(f"Ошибка при обращении к сервису Whisper: {str(e)}")
