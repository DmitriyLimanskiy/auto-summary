# Changelog

Все значимые изменения проекта фиксируются в этом файле.
Версия приложения дублируется в `backend/main.py` (`FastAPI(..., version=...)`).

## [0.2.0] — 2026-09-13

### Добавлено

- `POST /api/v1/models/import` — импорт `.gguf`-модели из директории `/models`
  в Ollama через нативный `ollama.AsyncClient` (`create_blob` → `create`
  с `parameters: {temperature, num_ctx}`).
- Схема `CreateModelRequest` (`backend/src/shemas/models.py`): `model_name`,
  `gguf_file`, опциональные `temperature` / `num_ctx`.
- Зависимость `ollama==0.6.2` в `backend/requirements.txt`.
- Переменная окружения `OLLAMA_SERVER_URL` (дефолт `http://llm-server:11434`) —
  host нативного API Ollama без суффикса `/v1`.
- Документация кода: docstrings и комментарии во всех модулях `backend/`
  (`main.py`, `src/config.py`, `src/audio.py`, `src/stt.py`, `src/llm.py`,
  `src/shemas/models.py`).
- Раздел `POST /api/v1/models/import` в `README.md`, обновлены таблицы
  переменных окружения, зависимостей и структура проекта.

## [0.1.0] — 2026-09-07

### Добавлено

- Пайплайн `POST /api/v1/meeting/process`: Upload → FFmpeg (WAV 16 kHz mono)
  → faster-whisper-server (STT, `ru`) → Ollama (саммари в Markdown) →
  сохранение `.md` в `storage/summaries/`.
- `GET /health`: проверка доступности Whisper и Ollama (200 `ok` / 503 `degraded`).
- Docker-окружение: `backend` (FastAPI :8080), `whisper-server` (:8000),
  `llm-server` (Ollama :11434), сеть `auto-summary-network`,
  volumes `whisper_cache` / `ollama_storage`, bind-mount `./backend/storage`.
- Системные промпты `sys_prompt_1.txt` (резюме встречи) и `sys_prompt_2.txt`
  (конспект лекции, используется по умолчанию).
