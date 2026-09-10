# Auto-Summary

Автоматическое создание конспекта лекции / резюме встречи из аудио/видео записей.

Пайплайн: `Upload (mp4/mp3/...)` → `FFmpeg → WAV 16kHz mono` → `faster-whisper-server (STT, lang=ru)` →
`Ollama (LLM, OpenAI-совместимый API)` → `Markdown-конспект + сохранение на диск`.

## Архитектура

```text
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│   Client    │────▶│  Backend    │────▶│ Whisper (STT)    │
│  (Upload)   │     │  (FastAPI)  │     │ faster-whisper   │
└─────────────┘     │  :8080      │     │ server :8000     │
                    └──────┬──────┘     └──────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌─────────────┐ ┌───────────┐ ┌──────────────┐
     │ Ollama LLM  │ │ FFmpeg    │ │ storage/     │
     │ :11434      │ │ WAV 16kHz │ │ uploads/audio│
     │ (OpenAI API)│ │ mono      │ │ /summaries   │
     └─────────────┘ └───────────┘ └──────────────┘
```

Что делает Backend (`backend/main.py`):

1. Сохраняет загруженный файл в `storage/uploads/` (потоково, чанками по 1 МБ).
2. Извлекает аудио через FFmpeg в `storage/audio/<name>.wav` (`WAV, mono, 16 kHz, pcm_s16le` — оптимально для Whisper),
   см. `backend/src/audio.py`.
3. Транскрибирует через Whisper (`model="whisper-1"`, `language="ru"`), см. `backend/src/stt.py`.
4. Генерирует конспект через LLM (`temperature=0.2`, системный промпт `src/prompts/sys_prompt_2.txt`), см.
   `backend/src/llm.py`.
5. Сохраняет результат в `storage/summaries/<name> summary.md` и возвращает JSON с `summary_markdown` и`raw_transcript`.

> В коде есть два промпта: `sys_prompt_1.txt` — резюме встречи (Executive Summary, решения, Action Items),
`sys_prompt_2.txt` — подробный учебный конспект лекции. По умолчанию используется `sys_prompt_2.txt`.

## Сервисы

| Сервис  | Контейнер              | Порт хоста | Описание                                               |
|---------|------------------------|------------|--------------------------------------------------------|
| Backend | `auto-summary-backend` | 8080       | FastAPI приложение (`python:3.14-slim` + FFmpeg)       |
| Whisper | `whisper_stt_server`   | 8000       | `fedirz/faster-whisper-server:latest-cuda` (STT)       |
| Ollama  | `ollama_llm_server`    | 11434      | `ollama/ollama:latest` (LLM, OpenAI-совместимый `/v1`) |

Сеть: `auto-summary-network` (bridge). Volumes: `whisper_cache` (кэш HF-модели), `ollama_storage` (`/root/.ollama`),
bind-mount `./backend/storage` → `/app/storage` (загрузки, аудио, конспекты сохраняются на хосте).

## Требования

- Docker + Docker Compose
- Python 3.14+ и FFmpeg — только для локальной разработки без Docker (в Docker-образе FFmpeg уже установлен)
- NVIDIA Driver + NVIDIA Container Toolkit — опционально, для ускорения Whisper/Ollama на GPU. Без GPU уберите
  `deploy.resources.reservations.devices` из `docker-compose.yml` или используйте CPU-образы.

## Быстрый старт

### 1. Клонирование

```bash
git clone <repo-url> auto-summary
cd auto-summary
```

### 2. Настройка переменных окружения

Шаблон лежит в `backend/.env.example`, рабочий файл — `backend/.env` (не коммитится, см. `.gitignore`):

```bash
cp backend/.env.example backend/.env
```

При необходимости отредактируйте `backend/.env`. Для запуска в Docker Compose со значениями по умолчанию достаточно:

```env
WHISPER_SERVER_URL=http://whisper-server:8000/v1
WHISPER_SERVER_URL_MODELS=http://whisper-server:8000/v1/models
WHISPER_API_KEY=not-needed

LLM_SERVER_URL=http://llm-server:11434/v1
LLM_SERVER_URL_MODELS=http://llm-server:11434/v1/models
LLM_API_KEY=not-needed
DEFAULT_MODEL_ID=qwen3.5-custom:latest
```

> Внутри Compose сервисы обращаются друг к другу по именам (`http://whisper-server:8000`, `http://llm-server:11434`).
`localhost` используется только с хоста. В `backend/.env` для локального запуска без Docker укажите
`http://localhost:8000/v1` и `http://localhost:11434/v1`.

### 3. Запуск через Docker Compose

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
```

Остановка (volumes с моделями сохраняются):

```bash
docker compose down
```

Полное удаление данных (модели скачаются заново!):

```bash
docker compose down -v
```

### 4. Установка LLM-модели в Ollama

Ollama запускается в отдельном контейнере, модели не входят в образ:

```bash
docker exec -it ollama_llm_server ollama pull qwen3.5:latest
docker exec -it ollama_llm_server ollama list
```

Модель сохраняется в volume `ollama_storage`.

Своя модель из `Modelfile` (директория `./models` смонтирована как `/models`):

```bash
docker exec -it ollama_llm_server ollama create qwen3.5-custom -f /models/Modelfile
docker exec -it ollama_llm_server ollama list
```

Текущий `models/Modelfile`:

```text
FROM /models/Qwen3.5-9B-Q4_K_M.gguf

PARAMETER temperature 0.8
PARAMETER num_ctx 24576
```

Положите `.gguf`-файл рядом с `Modelfile` и укажите имя в `.env`:

```env
DEFAULT_MODEL_ID=qwen3.5-custom:latest
```

> `DEFAULT_MODEL_ID` сейчас читается в `src/config.py`, но `POST /api/v1/meeting/process` пока использует дефолт
> параметра `model_id="qwen3.5-custom:latest"` — передавайте `model_id` явно в форме запроса.

Интерактивная проверка модели:

```bash
docker exec -it ollama_llm_server ollama run qwen3.5-custom:latest
```

### 5. Whisper STT

В `docker-compose.yml` задано:

```yaml
image: fedirz/faster-whisper-server:latest-cuda
environment:
  WHISPER__MODEL: deepdml/faster-whisper-large-v3-turbo-ct2
```

Модель скачивается при первом старте в volume `whisper_cache`. Первый запуск может занять несколько минут.

Проверка:

```bash
docker logs -f whisper_stt_server
curl http://localhost:8000/v1/models
```

Backend всегда запрашивает транскрибацию с `language="ru"` и `model="whisper-1"` (фиксировано для OpenAI-совместимости).

### 6. Проверка

```bash
curl http://localhost:8080/health
```

Пример ответа (все зависимости доступны):

```json
{
  "status": "ok",
  "dependencies": {
    "whisper": "healthy",
    "ollama": "healthy"
  }
}
```

Если Whisper/Ollama недоступны — статус `degraded` и HTTP `503`.

Swagger UI (FastAPI по умолчанию): `http://localhost:8080/docs`.

## API

### `POST /api/v1/meeting/process` — обработка встречи/лекции

Принимает `multipart/form-data`: файл `file` + опциональное текстовое поле `model_id`.

```bash
curl -X POST "http://localhost:8080/api/v1/meeting/process" \
  -F "file=@meeting.mp4" \
  -F "model_id=qwen3.5-custom:latest"
```

Поддерживается любой формат, который понимает FFmpeg (mp4, mkv, webm, mp3, wav, m4a и т.д.).

**Успешный ответ (200):**

```json
{
  "task_id": "meeting",
  "status": "COMPLETED",
  "original_filename": "meeting.mp4",
  "summary_file": "meeting summary.md",
  "summary_markdown": "# Название лекции\n\n...",
  "raw_transcript": "Полный текст транскрибации..."
}
```

- `task_id` = имя файла без расширения.
- `summary_file` сохраняется в `backend/storage/summaries/` (в контейнере `/app/storage/summaries/`).

**Ошибки:**

| Код | Когда                                                                                                                                                                                                 |
|-----|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 400 | файл не загружен / пустое имя                                                                                                                                                                         |
| 500 | ошибка сохранения файла, ошибка FFmpeg (`Не удалось извлечь аудиодорожку`), ошибка Whisper (`Не удалось транскрибировать аудио`), ошибка LLM (`Не удалось сгенерировать резюме`), ошибка записи `.md` |

### `GET /health` — проверка зависимостей

Проверяет `WHISPER_SERVER_URL_MODELS` и `LLM_SERVER_URL_MODELS` с таймаутом 3 c:

```bash
curl -i http://localhost:8080/health
```

- `200 {"status":"ok", ...}` — обе зависимости `healthy`.
- `503 {"status":"degraded", ...}` — хотя бы одна `unhealthy`/`unreachable`.

## Локальная разработка

### Backend без Docker (нужны запущенные Whisper + Ollama)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # и при необходимости поправьте URL на localhost
uvicorn main:app --reload --port 8080
```

Зависимости (`requirements.txt`): `fastapi`, `uvicorn`, `openai` (используется как клиент и к Whisper, и к Ollama),
`httpx`, `pydantic`, `python-multipart`, `python-ffmpeg` (требует системный `ffmpeg`).

### Только Backend в Docker (dev)

`docker-compose.dev.yml` собирает только `backend` с bind-mount `./backend:/app` для live-правок:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

> Dev-файл рассчитан на внешний Whisper/Ollama — задайте URL в `backend/.env`.

## Переменные окружения

Файлы: шаблон `backend/.env.example`, рабочий `backend/.env` (подключается через `env_file` в Compose).

| Переменная                  | Описание                                   | По умолчанию в примере                 |
|-----------------------------|--------------------------------------------|----------------------------------------|
| `WHISPER_SERVER_URL`        | Base URL Whisper (OpenAI-совместимый)      | `http://whisper-server:8000/v1`        |
| `WHISPER_SERVER_URL_MODELS` | URL списка моделей Whisper (для `/health`) | `http://whisper-server:8000/v1/models` |
| `WHISPER_API_KEY`           | Ключ для Whisper (формальность)            | `not-needed`                           |
| `LLM_SERVER_URL`            | Base URL Ollama (OpenAI-совместимый)       | `http://llm-server:11434/v1`           |
| `LLM_SERVER_URL_MODELS`     | URL списка моделей Ollama (для `/health`)  | `http://llm-server:11434/v1/models`    |
| `LLM_API_KEY`               | Ключ для Ollama (формальность)             | `not-needed`                           |
| `DEFAULT_MODEL_ID`          | Модель LLM по умолчанию                    | `qwen3.5-custom:latest`                |

Дополнительно `docker-compose.yml` задаёт `WHISPER_SERVER_URL` / `WHISPER_SERVER_URL_MODELS` / `LLM_SERVER_URL` /
`LLM_SERVER_URL_MODELS` в `environment` сервиса `backend` (имеют приоритет над `backend/.env`, внутри сети указывают
на имена сервисов `whisper-server` / `llm-server`).

Порты с хоста: `8080` (backend), `8000` (whisper), `11434` (ollama).

## GPU

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
```

Если GPU видна из Docker — `whisper-server` и `llm-server` из `docker-compose.yml` используют её автоматически (секция
`deploy.resources.reservations`). Для CPU-хоста удалите эти секции и при необходимости смените образ Whisper на нек
CUDA-вариант.

## Структура проекта

```text
auto-summary/
├── docker-compose.yml      # backend + whisper-server + llm-server (prod)
├── docker-compose.dev.yml  # только backend с bind-mount (не коммитится)
├── models/
│   └── Modelfile           # сборка своей Ollama-модели (FROM *.gguf)
├── backend/
│   ├── Dockerfile          # python:3.14-slim + ffmpeg + uvicorn :8080
│   ├── main.py             # FastAPI: POST /api/v1/meeting/process, GET /health
│   ├── requirements.txt
│   ├── env.example         # шаблон конфигурации
│   ├── .env                # локальная конфигурация (не коммитится)
│   ├── src/
│   │   ├── config.py       # env-конфиг + logger
│   │   ├── audio.py        # FFmpeg → WAV 16kHz mono
│   │   ├── stt.py          # Whisper-клиент (ru, whisper-1)
│   │   ├── llm.py          # Ollama-клиент (temperature 0.2, sys_prompt_2)
│   │   └── prompts/
│   │       ├── sys_prompt_1.txt  # резюме встречи
│   │       └── sys_prompt_2.txt  # конспект лекции (используется)
│   └── storage/            # создаётся автоматически, не коммитится
│       ├── uploads/        # исходные файлы
│       ├── audio/          # извлечённый WAV
│       └── summaries/      # итоговые *.md
```

## Управление контейнерами

```bash
docker compose up -d --build backend   # пересобрать только backend
docker compose restart backend whisper-server llm-server
docker compose ps
docker compose logs -f backend
docker compose logs -f whisper-server
docker compose logs -f llm-server
docker compose down        # остановить, volumes сохранить
docker compose down -v     # остановить + удалить ollama_storage, whisper_cache
```

## Работа с моделями Ollama

```bash
docker exec -it ollama_llm_server ollama pull <model>
docker exec -it ollama_llm_server ollama list
docker exec -it ollama_llm_server ollama rm <model>
docker exec -it ollama_llm_server ollama create <model-name> -f /models/Modelfile
docker exec -it ollama_llm_server ollama run <model>
```

## Известные ограничения / TODO

- `DEFAULT_MODEL_ID` из `.env` не подставляется автоматически в `POST /api/v1/meeting/process` — нужно передавать
  `model_id` в запросе.
- Обработка синхронная: большой файл блокирует запрос на время STT+LLM (смотрите логи
  `Время выполнения process_meeting`).
- `storage/` смонтирован в контейнер (`./backend/storage:/app/storage`), файлы `uploads` / `audio` / `summaries`
  сохраняются на хосте и переживают пересоздание контейнера.
- Нет автотестов.
