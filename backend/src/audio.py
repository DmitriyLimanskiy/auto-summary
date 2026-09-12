"""Извлечение аудиодорожки из медиафайлов через FFmpeg."""

from pathlib import Path

from ffmpeg import FFmpeg


def extract_audio_from_video(input_path: Path, output_path: Path) -> Path:
    """
    Извлекает аудиодорожку из видео/аудио файла и конвертирует ее
    в WAV (16kHz, mono), оптимальный для Whisper.

    Args:
        input_path: путь к исходному медиафайлу (любой формат FFmpeg).
        output_path: путь для сохранения результата (обычно <name>.wav).

    Returns:
        Тот же output_path после успешной конвертации.

    Raises:
        RuntimeError: если FFmpeg завершился с ошибкой.
    """
    try:
        # Параметры подобраны под Whisper: mono, 16 kHz, PCM 16-bit.
        ffmpeg = (
            FFmpeg()
            .input(str(input_path))
            .output(
                str(output_path),
                format='wav',
                ac=1,
                ar='16000',
                acodec='pcm_s16le'
            )
        )

        # Синхронный запуск FFmpeg; вывод команды печатаем в stdout для отладки.
        print(ffmpeg.execute())

        return output_path

    except Exception as e:
        raise RuntimeError(f"Ошибка FFmpeg при конвертации аудио")
