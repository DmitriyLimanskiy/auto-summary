# Changelog

Все значимые изменения проекта фиксируются в этом файле.
Версия приложения дублируется в `backend/main.py` (`FastAPI(..., version=...)`).

## [0.2.1] — 2026-09-13

### Добавлено

- Поле `overwrite` в `CreateModelRequest` (`backend/src/shemas/models.py`):
  `false` (по умолчанию) — повторный импорт с занятым `model_name` отклоняется
  с `409 Conflict`; `true` — старая модель удаляется перед созданием.
- Флаг `replaced` в ответе `POST /api/v1/models/import` (`true` — старая модель
  была удалена, `false` — создана новая).
- Хелпер `delete_model_if_exists` (`backend/main.py`): проверка через
  `ollama_client.show`, удаление существующей модели (404 — модели нет).

### Изменено

- `temperature` / `num_ctx` со значением `null` не отправляются в Ollama
  (применяются дефолты сервера), раньше уходили как явный `null`.
- `ollama_response` в ответе ручки сериализуется через `model_dump()`
  (раньше возвращался сырой `ProgressResponse`).
- Ошибки импорта структурированы: ошибки нативного API Ollama (`ResponseError`)
  проксируют свой HTTP-статус, `detail` — словарь `{type, message}`;
  прочие исключения — `500` с `{type, message, repr}`.
- Обработчик ручки переименован: `create_custom_model` → `import_custom_model`.
- `docker-compose.dev.yml` удалён из репозитория, dev compose-файлы
  (`docker-compose.dev*.yml`) теперь локальные и игнорируются через `.gitignore`
  (паттерны исправлены на нижний регистр — заглавные не работали на Linux).
- Версия `0.2.0` → `0.2.1` в `backend/main.py`.

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
