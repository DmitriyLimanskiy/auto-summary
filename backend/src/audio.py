from pathlib import Path

from ffmpeg import FFmpeg


def extract_audio_from_video(input_path: Path, output_path: Path) -> Path:
    """
    Извлекает аудиодорожку из видео/аудио файла и конвертирует ее
    в WAV (16kHz, mono), оптимальный для Whisper.
    """
    try:
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

        print(ffmpeg.execute())

        return output_path

    except Exception as e:
        raise RuntimeError(f"Ошибка FFmpeg при конвертации аудио")
