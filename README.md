# Auto-Summary

Автоматическое создание конспекта лекции / резюме встречи из аудио/видео записей.

Пайплайн: `Upload (mp4/mp3/...)` → `FFmpeg → WAV 16kHz mono` → `faster-whisper-server (STT, lang=ru)` →
`Ollama (LLM, OpenAI-совместимый API)` → `Markdown-конспект + сохранение на диск`.

Всё управление — через ручки backend (Swagger UI: `http://localhost:8080/docs`).

## Основной сценарий

1. Запустите стек (`docker compose up -d --build`) и проверьте зависимости — `GET /health`.
2. Импортируйте модель в Ollama — `POST /api/v1/models/import` (`.gguf`-файл должен лежать в `./models/`).
3. Загрузите запись и получите конспект — `POST /api/v1/meeting/process`.

Подробности по каждой ручке — в разделе [API](#api).

## Архитектура

```text
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│   Client    │────▶│  Backend    │────▶│ Whisper (STT)    │
│ (Swagger /  │     │  (FastAPI)  │     │ faster-whisper   │
│  API)       │     │  :8080      │     │ server :8000     │
└─────────────┘     └──────┬──────┘     └──────────────────┘
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
6. Импортирует `.gguf`-модель из директории `/models` в Ollama (`POST /api/v1/models/import`): заливка blob через
   нативный `ollama.AsyncClient` + создание модели с `temperature`/`num_ctx` из запроса, см.
   `backend/src/shemas/models.py`.

> В коде два промпта: `sys_prompt_1.txt` — резюме встречи (Executive Summary, решения, Action Items),
`sys_prompt_2.txt` — подробный учебный конспект лекции. По умолчанию используется `sys_prompt_2.txt`.

## Сервисы

| Сервис  | Контейнер              | Порт хоста | Описание                                               |
|---------|------------------------|------------|--------------------------------------------------------|
| Backend | `auto-summary-backend` | 8080       | FastAPI приложение (`python:3.14-slim` + FFmpeg)       |
| Whisper | `whisper_stt_server`   | 8000       | `fedirz/faster-whisper-server:latest-cuda` (STT)       |
| Ollama  | `ollama_llm_server`    | 11434      | `ollama/ollama:latest` (LLM, OpenAI-совместимый `/v1`) |

Сеть `auto-summary-network` (bridge). Данные: `whisper_cache` (кэш STT-модели, скачивается при первом старте —
займет несколько минут), `ollama_storage` (`/root/.ollama`), `./backend/storage` → `/app/storage`,
`./models` → `/models` (доступна и backend, и Ollama).

## Требования

- Docker + Docker Compose.
- Python 3.14+ и FFmpeg — только для локальной разработки без Docker.
- GPU (NVIDIA Driver + Container Toolkit) — опционально. Для CPU-хоста удалите секции
  `deploy.resources.reservations.devices` из `docker-compose.yml` (и при необходимости смените образ Whisper
  на не-CUDA вариант).

## Быстрый старт

```bash
git clone <repo-url> auto-summary
cd auto-summary
cp backend/.env.example backend/.env   # дефолтов достаточно для запуска в Compose
docker compose up -d --build
```

Дальше — по основному сценарию через Swagger UI (`http://localhost:8080/docs`):
сначала `GET /health`, затем `POST /api/v1/models/import`, затем `POST /api/v1/meeting/process`.

Остановка: `docker compose down` (данные сохраняются), полное удаление данных: `docker compose down -v`.

> Внутри Compose сервисы обращаются друг к другу по именам (`whisper-server`, `llm-server`).
> Для локального запуска backend без Docker укажите в `backend/.env` `localhost`-адреса
> (пример — в `backend/.env.example`), включая `OLLAMA_SERVER_URL=http://localhost:11434` (без `/v1`).

## API

### `GET /health` — проверка зависимостей

Опрашивает `WHISPER_SERVER_URL_MODELS` и `LLM_SERVER_URL_MODELS` с таймаутом 3 c.

Ответ `200` — всё доступно:

```json
{
  "status": "ok",
  "dependencies": {
    "whisper": "healthy",
    "ollama": "healthy"
  }
}
```

Если хотя бы одна зависимость недоступна — статус `degraded` и HTTP `503`.

### `POST /api/v1/models/import` — импорт `.gguf`-модели в Ollama

Тело запроса (`CreateModelRequest`, см. `backend/src/shemas/models.py`):

```json
{
  "model_name": "qwen3.5-custom:latest",
  "gguf_file": "Qwen3.5-9B-Q4_K_M.gguf",
  "temperature": 0.8,
  "num_ctx": 24576
}
```

- `gguf_file` — имя файла внутри `/models` (положите `.gguf` в `./models/` на хосте).
- `temperature` / `num_ctx` опциональны (`null` — Ollama применит свои дефолты).

Ручка заливает файл в Ollama как blob (`create_blob` → `digest`) и создаёт модель (`create`)
с `parameters: {temperature, num_ctx}` через нативный `ollama.AsyncClient` (`OLLAMA_SERVER_URL`).

Успешный ответ (`200`):

```json
{
  "message": "Модель 'qwen3.5-custom:latest' создана",
  "digest": "sha256:...",
  "ollama_response": {}
}
```

Ошибки: `404` — `.gguf`-файл не найден в `/models`; `500` — ошибка Ollama.

> Альтернативный способ — классический `Modelfile` (`./models/Modelfile`): `FROM /models/*.gguf` + `PARAMETER`.
> В `docker-compose.dev.yml` директория `./models` не смонтирована — добавьте `- ./models:/models` вручную.

### `POST /api/v1/meeting/process` — обработка встречи/лекции

Форма `multipart/form-data`: файл `file` + текстовое поле `model_id` (например, `qwen3.5-custom:latest` —
имя модели, созданной ручкой выше). Формат файла — любой, понятный FFmpeg
(mp4, mkv, webm, mp3, wav, m4a и т.д.).

Успешный ответ (`200`):

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
- `summary_file` сохраняется в `backend/storage/summaries/`.

Ошибки: `400` — файл не загружен / пустое имя; `500` — ошибка сохранения файла, FFmpeg
(`Не удалось извлечь аудиодорожку`), Whisper (`Не удалось транскрибировать аудио`), LLM
(`Не удалось сгенерировать резюме`) или записи `.md`.

> `DEFAULT_MODEL_ID` из `.env` пока не подставляется автоматически — передавайте `model_id` в запросе явно.

## Локальная разработка

Backend без Docker (нужны запущенные Whisper + Ollama):

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # и при необходимости поправьте URL на localhost
uvicorn main:app --reload --port 8080
```

Только backend в Docker (dev, с live-правками через bind-mount `./backend:/app`):

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

> Dev-окружение рассчитано на внешние Whisper/Ollama — задайте URL в `backend/.env`.

## Переменные окружения

Шаблон — `backend/.env.example`, рабочий файл — `backend/.env` (не коммитится).
В `docker-compose.yml` часть переменных продублирована в `environment` сервиса `backend`
(имеют приоритет, указывают на имена сервисов внутри сети).

| Переменная                  | Описание                                                    |
|-----------------------------|-------------------------------------------------------------|
| `WHISPER_SERVER_URL`        | Base URL Whisper (OpenAI-совместимый), напр. `http://whisper-server:8000/v1` |
| `WHISPER_SERVER_URL_MODELS` | URL списка моделей Whisper (для `/health`)                  |
| `WHISPER_API_KEY`           | Ключ для Whisper (формальность, `not-needed`)               |
| `LLM_SERVER_URL`            | Base URL Ollama (OpenAI-совместимый), напр. `http://llm-server:11434/v1` |
| `LLM_SERVER_URL_MODELS`     | URL списка моделей Ollama (для `/health`)                   |
| `LLM_API_KEY`               | Ключ для Ollama (формальность, `not-needed`)                |
| `OLLAMA_SERVER_URL`         | Host нативного API Ollama без `/v1` (для `/models/import`)  |
| `DEFAULT_MODEL_ID`          | Модель LLM по умолчанию (`qwen3.5-custom:latest`)           |

## Структура проекта

```text
auto-summary/
├── CHANGELOG.md              # история версий
├── docker-compose.yml      # backend + whisper-server + llm-server (prod)
├── docker-compose.dev.yml  # только backend с bind-mount (dev)
├── models/                   # .gguf-файлы и Modelfile → /models в контейнерах
├── backend/
│   ├── Dockerfile          # python:3.14-slim + ffmpeg + uvicorn :8080
│   ├── main.py             # FastAPI: /meeting/process, /models/import, /health
│   ├── requirements.txt
│   ├── .env.example        # шаблон конфигурации
│   ├── .env                # локальная конфигурация (не коммитится)
│   ├── src/
│   │   ├── config.py       # env-конфиг + logger
│   │   ├── audio.py        # FFmpeg → WAV 16kHz mono
│   │   ├── stt.py          # Whisper-клиент (ru, whisper-1)
│   │   ├── llm.py          # Ollama-клиент (temperature 0.2, sys_prompt_2)
│   │   ├── shemas/
│   │   │   └── models.py   # схемы запросов (CreateModelRequest)
│   │   └── prompts/
│   │       ├── sys_prompt_1.txt  # резюме встречи
│   │       └── sys_prompt_2.txt  # конспект лекции (используется)
│   └── storage/            # создаётся автоматически, не коммитится
│       ├── uploads/        # исходные файлы
│       ├── audio/          # извлечённый WAV
│       └── summaries/      # итоговые *.md
```

## Известные ограничения

- Обработка синхронная: большой файл блокирует запрос на время STT+LLM (смотрите логи
  `Время выполнения process_meeting`).
- `storage/` переживает пересоздание контейнера (bind-mount на хост).
- Нет автотестов.
