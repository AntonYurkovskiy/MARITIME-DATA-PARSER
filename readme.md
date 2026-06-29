# Maritime Data Parser

Инструмент для массовой загрузки данных моряков из HTML-резюме в систему 360Crew через REST API.

Парсит HTML-файлы, нормализует данные, валидирует и отправляет по блокам:
основная информация, адреса, родственники, контракты, документы, фото.

---

## Быстрый старт

### 1. Клонировать и создать окружение

```bash
git clone <repo-url>
cd staff
python -m venv venv
venv\\Scripts\\activate        # Windows
pip install -r requirements.txt
```

### 2. Настроить переменные окружения

```bash
copy .env.example .env
```

Заполнить `.env`:

```env
CREWING_EMAIL=your_email@example.com
CREWING_PASSWORD=your_password
API_BASE_URL=https://staffdev.360crewing.com/api/v1
```

### 3. Положить HTML-файлы в `out/out_min/`

Или задать другую директорию через `INPUT_DIR` в `.env`.

### 4. Запустить

```bash
python main_orchestration.py
```

---

## Переменные окружения

| Переменная | Обязательная | По умолчанию | Описание |
|---|:---:|---|---|
| `CREWING_EMAIL` | да | — | Email для авторизации в API |
| `CREWING_PASSWORD` | да | — | Пароль для авторизации в API |
| `API_BASE_URL` | нет | `https://staffdev.360crewing.com/api/v1` | Базовый URL API |
| `INPUT_DIR` | нет | `out/out_min` | Папка с HTML-файлами (поддерживает вложенные) |
| `REPROCESS_ALL` | нет | — | `true` — сбросить дедупликацию и перезапустить все файлы |
| `DISABLE_CACHE` | нет | — | `true` — отключить persistent cache (для тестов) |

---

## Команды запуска

```powershell
# Обычный запуск (уже обработанные файлы пропускаются)
python main_orchestration.py

# Сбросить дедупликацию и обработать все файлы заново
$env:REPROCESS_ALL="true"; python main_orchestration.py

# Очистить загруженные записи с сервера (из последнего отчёта)
python clean_remote_base.py --force

# Очистить все записи с сервера (загрузить список с сервера)
python clean_remote_base.py --from-server-list --force

# Dry-run — показать что будет удалено, без удаления
python clean_remote_base.py --dry-run
```

---

## Структура каталогов

```
staff/
├── main_orchestration.py       # Основная точка запуска
├── main.py                     # [DEPRECATED] legacy-скрипт, только для справки
├── clean_remote_base.py        # Утилита очистки записей на сервере
├── requirements.txt            # Прод-зависимости
├── requirements-dev.txt        # Dev-зависимости (pytest, ruff, mypy)
├── .env.example                # Шаблон переменных окружения
│
├── src/
│   ├── api/                    # HTTP-клиенты к 360Crew API
│   │   ├── client.py           # Сессия, авторизация, retry-стратегия
│   │   ├── seafarers.py        # CRUD моряков, поиск ID в словарях
│   │   ├── vessels.py          # Поиск судов по имени (fuzzy match)
│   │   ├── dicts.py            # Работа со справочниками API
│   │   └── geo.py              # Геопоиск (страны, города)
│   │
│   ├── cache/
│   │   └── persistent_cache.py # SQLite-кэш (TTL) + ProcessedFilesTracker
│   │
│   ├── orchestration/
│   │   ├── blocks_config.yaml  # Конфигурация блоков (enabled, order, endpoint...)
│   │   ├── pipeline.py         # Ядро: запуск блоков, отправка, таймеры
│   │   ├── registry.py         # Реестр функций-обработчиков
│   │   ├── loader.py           # Загрузка blocks_config.yaml
│   │   ├── blocks.py           # Типы данных: BlockSpec, BlockResult, SyncStatus
│   │   ├── result.py           # Логирование результатов, сохранение отчёта
│   │   └── strategies/         # Блок-стратегии (parse / normalize / validate / build)
│   │       ├── main_info.py
│   │       ├── addresses.py
│   │       ├── relatives.py
│   │       ├── contracts.py    # sea_service блок
│   │       ├── documents.py
│   │       └── photo.py
│   │
│   ├── parsers/
│   │   ├── html.py             # Парсинг HTML-таблиц в dict-секции
│   │   └── photo.py            # Извлечение base64-фото из HTML
│   │
│   ├── extractors/             # Извлечение конкретных полей из raw-данных
│   ├── domain/                 # Бизнес-логика: builder, языки, маппинги
│   ├── utils/                  # Валидаторы, утилиты
│   └── config.py               # Чтение env-переменных
│
├── tests/                      # pytest-тесты (395 тестов)
├── orchestration_results/      # JSON-отчёты каждого запуска
└── out/out_min/                # HTML-файлы для обработки (INPUT_DIR)
```

---

## Архитектура пайплайна

```
blocks_config.yaml
      |
      v
   loader.py  -->  список BlockSpec (имя, endpoint, method, depends_on, ...)
      |
      v
  pipeline.py  -->  для каждого файла:
      |               1. parse     (raw HTML -> dict)
      |               2. normalize (dict -> нормализованный dict + API lookup)
      |               3. validate  (проверка обязательных полей)
      |               4. build     (-> payload для API)
      |               5. send      (POST/PUT -> 360Crew API)
      |
      v
  result.py   -->  JSON-отчёт + лог
```

**Кэширование:** словари API кэшируются в SQLite (`cache.db`, TTL 24ч).  
**Дедупликация:** обработанные файлы записываются в `cache.db` — повторный запуск пропускает их автоматически.  
**Retry:** автоматически повторяет запросы при 429/502/503/504 (до 10 попыток, backoff 1s).

---

## Запуск тестов

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Добавление нового блока

1. Создать `src/orchestration/strategies/my_block.py` с функциями:
   `parse_my_block_raw`, `normalize_my_block`, `validate_my_block`, `build_my_block_payload`
2. Зарегистрировать в `src/orchestration/registry.py` -> `populate_default_registry()`
3. Добавить секцию в `src/orchestration/blocks_config.yaml` с `enabled: true`