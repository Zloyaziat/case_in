# case_in — ИИ-помощник принятия решений для химического производства

Система ведёт **партию** (один производственный цикл) по заранее заданной **формуле**: шаг за шагом
принимает показания датчиков, усредняет их по коротким окнам, сравнивает с **эталонными партиями**
и при отклонении выдаёт оператору рекомендацию:

> Нужно увеличить массу лактида до 139.65 кг на датчике D-LAC-04!

Кроме партий, в проекте есть приёмка и расчёт формул (масса конечного продукта по уравнениям
реакций) и отдельный модуль симуляции стадий.

| Слой | Технологии |
|---|---|
| Бэкенд | Python 3.13, FastAPI, SQLAlchemy 2 (async) + asyncpg, Pydantic 2 |
| База | PostgreSQL 17 |
| Фронтенд | React 19 + React Router 8 (SPA, `ssr: false`), Tailwind 4, Vite 8, TypeScript; в контейнере — nginx |
| Инфраструктура | Docker Compose: `postgres`, `backend`, `frontend`, `pgadmin` |

---

## Содержание

1. [Быстрый старт](#1-быстрый-старт)
2. [Локальная разработка](#2-локальная-разработка)
3. [Архитектура](#3-архитектура)
4. [Структура репозитория](#4-структура-репозитория)
5. [Словарь терминов](#5-словарь-терминов)
6. [База данных](#6-база-данных)
7. [Данные в дампе](#7-данные-в-дампе)
8. [Формулы и расчёт массы продукта](#8-формулы-и-расчёт-массы-продукта)
9. [Партии: от выбора формулы до завершения](#9-партии-от-выбора-формулы-до-завершения)
10. [Эмулятор OPC (txt-файл с показаниями)](#10-эмулятор-opc-txt-файл-с-показаниями)
11. [Усреднение по окнам](#11-усреднение-по-окнам)
12. [Сравнение с эталоном и рекомендации](#12-сравнение-с-эталоном-и-рекомендации)
13. [Симуляция стадий (модуль monitoring)](#13-симуляция-стадий-модуль-monitoring)
14. [Фронтенд (пульт оператора)](#14-фронтенд-пульт-оператора)
15. [API — полный справочник](#15-api--полный-справочник)
16. [Настройки и переменные окружения](#16-настройки-и-переменные-окружения)
17. [Тесты](#17-тесты)
18. [Работа с репозиторием](#18-работа-с-репозиторием)
19. [Принятые решения](#19-принятые-решения)
20. [Ограничения и известные проблемы](#20-ограничения-и-известные-проблемы)
21. [Частые проблемы](#21-частые-проблемы)

---

## 1. Быстрый старт

Нужен только Docker (Docker Desktop на Windows/macOS или Docker Engine + Compose на Linux).

```bash
docker compose up -d --build
```

Первая сборка занимает несколько минут (ставятся Python- и npm-зависимости), дальше — секунды.
Когда всё поднимется:

| Адрес | Что там |
|---|---|
| **http://localhost:3000** | **пульт оператора** (новый фронтенд) |
| http://localhost:3000/docs | Swagger бэкенда (nginx проксирует его с того же порта) |
| http://localhost:8000/docs | Swagger напрямую с бэкенда |
| http://localhost:5050 | pgAdmin (логин и пароль — в `.env.docker`) |
| `localhost:5433` | PostgreSQL снаружи контейнера (`postgres` / `postgres`, база `case_in`) |

### Что происходит при первом запуске

1. Стартует `postgres`. Volume `postgres_data` пустой, поэтому Postgres выполняет все файлы из `sql/`
   (смонтирована в `/docker-entrypoint-initdb.d`) — загружается дамп `sql/case_in.sql`.
2. `backend` ждёт, пока `postgres` станет **healthy**. Healthcheck — `pg_isready -h 127.0.0.1`:
   во время загрузки дампа Postgres слушает только unix-сокет, поэтому проверка не проходит, пока
   дамп не загружен до конца. Без этого бэкенд успел бы создать таблицы раньше дампа и загрузка упала бы.
3. `backend` при старте вызывает `init_db()`: создаёт недостающие таблицы и колонки (раздел 6.4).
4. `frontend` (nginx) отдаёт собранный пульт и проксирует `/api`, `/docs`, `/redoc`, `/openapi.json` на `backend`.

### Первая партия за минуту

1. Откройте http://localhost:3000 → **Партии**.
2. В форме «Новая партия» выберите формулу **«Мел» (id 15)** — поля сырья заполнятся из первой стадии формулы.
3. Выберите ускорение времени **×10** и запустите — откроется страница партии.
4. Через ~3 секунды все три стадии пройдены; в «Рекомендациях оператору» — две рекомендации
   (их специально заложены в файл эмулятора, раздел 10).
5. Введите выход и качество → «Завершить партию». Галочкой можно сразу сделать партию эталонной.

### Полезные команды

```bash
docker compose ps                    # что запущено
docker compose logs -f backend       # логи бэкенда, в том числе рекомендации по партиям
docker compose logs postgres         # тут видно, загрузился ли дамп
docker compose up -d --build backend # пересобрать только бэкенд после правок
docker compose down                  # остановить (данные сохраняются)
docker compose down -v               # остановить и УДАЛИТЬ базу; при следующем up дамп загрузится заново
```

> ⚠️ **Дамп грузится только в пустую базу.** Если `sql/case_in.sql` обновился, а volume уже есть, новые
> данные сами не появятся — нужен `docker compose down -v` (удалит все партии!) или ручная загрузка.
> Все файлы в `sql/` выполняются по алфавиту — не кладите туда черновики.

---

## 2. Локальная разработка

Удобно, когда правите код: бэкенд с `--reload`, фронтенд с горячей перезагрузкой.

### База

```bash
docker compose up -d postgres        # порт 5433 на localhost; дамп загрузится сам, если volume пустой
```

### Бэкенд

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://localhost:8000, Swagger: /docs
```

Нужен Python **3.13** (как в `Dockerfile`). Строка подключения берётся из `.env`
(`postgresql+asyncpg://postgres:postgres@localhost:5433/case_in`); переменные окружения перекрывают `.env`.
Если `SQLALCHEMY_DATABASE_URL` не задан вовсе, используется SQLite-файл `./database.db` — но модели
используют `JSONB`, так что на практике нужен PostgreSQL.

### Фронтенд

```bash
cd frontend
bun install        # или: npm install
bun run dev        # http://localhost:3000
```

Dev-сервер Vite проксирует `/api` на `http://localhost:8000` (`vite.config.ts`), поэтому CORS не нужен.
Другой адрес бэкенда — переменная `BACKEND_URL`.

```bash
bun run typecheck  # react-router typegen && tsc
bun run build      # статика в frontend/build/client
```

---

## 3. Архитектура

```
                       Docker Compose
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                                                                              │
 │  frontend (nginx :80 → localhost:3000)                                       │
 │    /            → index.html (SPA, React Router)                             │
 │    /assets/*    → статика, кэш 7 дней                                        │
 │    /api/*       ─┐                                                           │
 │    /docs, /redoc,│ proxy_pass http://backend:8000                            │
 │    /openapi.json ┘                                                           │
 │                                                                              │
 │  backend (uvicorn :8000 → localhost:8000)                                    │
 │    FastAPI: /api/formulas, /api/sensors, /api/batches, /api/simulation       │
 │    фоновые задачи asyncio: живые партии, симуляция                           │
 │                         │                                                    │
 │                         ▼ asyncpg                                            │
 │  postgres (:5432 → 127.0.0.1:5433)    volume postgres_data                   │
 │    при первом старте: sql/case_in.sql                                        │
 │                                                                              │
 │  pgadmin (:80 → 127.0.0.1:5050)       volume pgadmin_data                    │
 └──────────────────────────────────────────────────────────────────────────────┘
```

**Главный принцип бэкенда:** логика расчётов написана без БД, asyncio и FastAPI
(`app/batches/process.py`, `reference.py`, `opc.py`, `app/monitoring/engine.py`, `plan.py`, `reference.py`,
`source.py`, `runner.py`, `app/calc.py`). Её тестируют на «искусственном» времени за миллисекунды.
Модули `session.py` / `manager.py` / `repo.py` только склеивают логику с часами и базой, а роутеры — с HTTP.

**Состояние живых процессов** (идущая партия, идущая симуляция) хранится в памяти процесса бэкенда,
результаты — в БД. Поэтому бэкенд запускается в **один** воркер (раздел 20).

---

## 4. Структура репозитория

```
case_in/
├── app/                              бэкенд (FastAPI)
│   ├── main.py                       приложение: lifespan (init_db, остановка фоновых задач), роутеры, статика
│   ├── models.py                     справочники: Formula, FormulaStep, Instrument, Sensor
│   ├── calc.py                       расчёт цепочки реакций: баланс, лимитирующий реагент, масса продукта
│   ├── database/
│   │   ├── __init__.py               реэкспорт Base, engine, async_session, get_db, init_db
│   │   └── db.py                     engine, сессии, init_db (create_all + ALTER для недостающих колонок)
│   ├── routers/
│   │   ├── formulas.py               /api/formulas — приёмка формул, список, детали, расчёт
│   │   ├── sensors.py                /api/sensors — список датчиков
│   │   ├── batches.py                /api/batches — партии (ядро MVP)
│   │   └── simulation.py             /api/simulation — симуляция стадий
│   ├── batches/                      ── партии (ядро MVP по ТЗ) ──
│   │   ├── models.py                 Batch, BatchStepWindow, BatchStep, BatchRecommendation
│   │   ├── opc.py                    эмулятор OPC: разбор txt, «проигрывание» строк по времени
│   │   ├── process.py                таймер шагов + усреднение по окнам (чистый Python)
│   │   ├── reference.py              выбор эталонов, сравнение, порог (чистый Python)
│   │   ├── repo.py                   загрузка из БД: шаги формулы, датчики, окна эталонных партий
│   │   └── session.py                живая партия: фоновая задача, тики, запись в БД, статус
│   ├── monitoring/                   ── симуляция стадий ──
│   │   ├── engine.py                 полосы допусков, эталонная кривая, проверка показания, текст сигнала
│   │   ├── plan.py                   план прогона: стадии, датчики, длительности
│   │   ├── reference.py              генерация синтетических эталонных партий
│   │   ├── source.py                 источники показаний: CSV-файл и синтетический генератор
│   │   ├── runner.py                 цикл прогона по стадиям с таймером
│   │   ├── repo.py                   БД: эталоны, план, запись показаний и сигналов
│   │   ├── manager.py                единственный активный прогон: старт/стоп/статус/журнал
│   │   └── models.py                 ReferenceBatchValue, SimRun, SimStepRun, SensorReading, SensorAlert
│   └── chemistry_steps/              устаревший роутер формул, в main.py не подключён
├── frontend/                         пульт оператора (React Router SPA), см. раздел 14
│   ├── app/
│   │   ├── root.tsx                  HTML-каркас, шрифты IBM Plex, ErrorBoundary
│   │   ├── routes.ts                 таблица маршрутов
│   │   ├── layouts/shell.tsx         шапка с навигацией, подвал
│   │   ├── routes/*.tsx              страницы: dashboard, sensors, formulas, formulas-import,
│   │   │                             batches, batch-detail, simulation, demo, about, not-found
│   │   ├── components/ui.tsx         PageHead, Panel, Chip, Notice, Spinner, Empty, TableScroll, StatBlock
│   │   ├── components/chart.tsx      SeriesChart (линейный график на SVG), Sparkline
│   │   ├── lib/api.ts                типизированный клиент всех эндпоинтов бэкенда
│   │   ├── lib/format.ts             форматирование чисел, времени, фаз, химических формул
│   │   ├── lib/usePoll.ts            периодический опрос API (пауза, когда вкладка скрыта)
│   │   └── app.css                   токены палитры (@theme) и компоненты (@layer components)
│   ├── public/                       favicon, formulas.json (пример формулы для приёмки)
│   ├── Dockerfile                    сборка (node 24) → nginx 1.27
│   ├── nginx.conf                    SPA + прокси /api и /docs на backend:8000
│   ├── package.json, bun.lock        зависимости (bun или npm)
│   ├── vite.config.ts                dev-сервер :3000, прокси /api, alias ~/ → app/
│   ├── react-router.config.ts        ssr: false, buildDirectory: build
│   ├── tsconfig.json
│   └── README.md                     краткое описание фронтенда
├── frontend-old/                     старые статические страницы (formulas.html, batches.html) — не раздаются
├── data/
│   ├── opc_formula15.txt             показания для эмулятора OPC (формула 15)
│   └── sensor_data_5000.csv          показания для симуляции (5000 строк, 57 датчиков, 11 стадий)
├── scripts/
│   └── make_opc_file.py              генератор opc_formula15.txt из эталонов в дампе
├── sql/
│   └── case_in.sql                   дамп БД (pg_dump 18): схема + данные
├── tests/
│   ├── test_batches.py               ядро партий + сквозной прогон формулы 15
│   └── test_monitoring.py            симуляция стадий
├── docker-compose.yml                postgres, backend, frontend, pgadmin
├── Dockerfile                        образ бэкенда (python:3.13-slim, uvicorn)
├── requirements.txt                  Python-зависимости (закреплённые версии)
├── .env                              настройки для локального запуска
├── .env.docker                       настройки для контейнеров
├── .dockerignore                     .git, .venv, __pycache__, .env — не попадают в образ бэкенда
└── .gitattributes                    LF для .sql/.sh/Dockerfile/.yml (важно на Windows)
```

---

## 5. Словарь терминов

| Термин | Значение |
|---|---|
| **Формула** | технологический процесс: название, версия, упорядоченные шаги (`formula` + `formula_steps`) |
| **Шаг / стадия** | одна реакция или операция процесса; у шага есть уравнение, массы, датчики и длительность. В коде партий — «шаг», в симуляции и на пульте — «стадия», это одно и то же |
| **Датчик (тег)** | измерительный канал, например `F-TT-01`; запись в `sensors`. Принадлежит прибору (`instruments`) |
| **Партия** | один запуск формулы на реальном (или эмулированном) оборудовании (`batch`) |
| **Окно** | короткий интервал (по умолчанию 2 с), за который показания датчика усредняются |
| **Эталонная партия** | завершённая партия с `is_reference = true`; с ней сравниваются новые партии |
| **Рекомендация** | текст оператору при отклонении среднего за окно от эталона |
| **v_in / v_finish** | сырьё на входе (по компонентам) / выход продукта |
| **Эмулятор OPC** | txt-файл с показаниями, который «проигрывается» вместо реального OPC-сервера |
| **Прогон (run)** | один запуск симуляции стадий (модуль monitoring), не путать с партией |
| **Полоса (band)** | допустимый диапазон значения датчика в момент стадии (симуляция) |

---

## 6. База данных

Всего 13 таблиц в трёх группах.

```
 СПРАВОЧНИКИ                      ПАРТИИ                               СИМУЛЯЦИЯ
 ───────────                      ──────                               ─────────
 formula ◄──┬── formula_steps     batch ──► formula                    sim_runs ──► formula
            │        ▲              ▲                                     ▲
            │        │              ├── batch_step                        ├── sim_step_runs ──► formula_steps
            │        │              ├── batch_step_window                 ├── sensor_readings ──► sensors
            │        │              └── batch_recommendations             └── sensor_alerts ──► sensor_readings
            │        └────────────────────────────────────────────────── reference_batch_values
 instruments ◄── sensors
```

Связь «шаг → датчики» не внешний ключ, а ключи JSON-поля `formula_steps.dict_plc_id` = `sensors.tag`.

### 6.1. Справочники (из дампа)

#### `formula` — формула

| Колонка | Тип | Описание |
|---|---|---|
| id | integer, PK, serial | |
| name | varchar, NOT NULL | название: «Мел» |
| version | integer, NOT NULL | версия |
| created_at | timestamptz, NOT NULL, default now() | |

Ограничения: `UNIQUE (name, version)` — `uq_formula_name_version`. Индекс `idx_formula_name_version`.

#### `formula_steps` — шаги формулы

| Колонка | Тип | Описание |
|---|---|---|
| id | integer, PK, serial | |
| formula_id | integer, NOT NULL, FK → formula.id `ON DELETE RESTRICT` | |
| step | integer, NOT NULL | номер шага, с 1 |
| step_key | varchar, NOT NULL | уравнение реакции: `CaO + H20` или `2C3H6O3 + CaCO3 -> Ca(C3H5O3)2 + H2O + CO2` |
| step_value | varchar, NOT NULL | целевой продукт шага: `Ca(OH)2` |
| in_data | jsonb, NOT NULL, default `{}` | массы реагентов до реакции, кг: `{"CaO": 62.5, "H20": 240.0}` |
| out_data | jsonb, NOT NULL, default `{}` | ожидаемые массы после, кг: `{"Ca(OH)2": 77.62, ...}` |
| dict_plc_id | jsonb, default `[]` | датчики шага и их диапазоны (формат ниже) |
| amount_time | interval | длительность шага (`00:00:10`, `1 day`) |
| constant | jsonb, default `{}` | множители к теоретической массе: `{"conversion": 0.98}` (раздел 8) |

Ограничения: `UNIQUE (formula_id, step)` — `uq_step_no`, `UNIQUE (formula_id, step_key)` — `uq_step_key`.
Индекс `idx_formula_steps_formula_id`. В модели SQLAlchemy колонка называется `dict_PLC_id`.

**Формат `dict_plc_id`:**

```json
{
  "F-TT-01": {
    "pre":    {"min": 35, "max": 40},
    "during": {"min": 35, "max": 40},
    "post":   {"min": 30, "max": 42}
  }
}
```

Ключ — `sensors.tag`; `pre` / `during` / `post` — допустимый диапазон до, во время и после шага
(любая фаза и любая граница может отсутствовать). Старый формат — просто список тегов `["F-TT-01"]` —
тоже понимается (без диапазонов).

#### `instruments` — приборы

| Колонка | Тип | Описание |
|---|---|---|
| id | integer, PK, serial | |
| name | text, NOT NULL | «Реактор с мешалкой», «Термосопротивление Pt100», … |

#### `sensors` — датчики

| Колонка | Тип | Описание |
|---|---|---|
| id | integer, PK, serial | |
| tag | text, NOT NULL, UNIQUE | тег: `D-LAC-04` |
| parameter | text, NOT NULL | измеряемая величина: «Масса лактида» (первое слово идёт в текст рекомендации) |
| instrument_id | integer, NOT NULL, FK → instruments.id `ON DELETE RESTRICT` | |
| unit | text, NOT NULL | единица: `кг`, `°C`, `бар изб.` |
| val_start, val_mid, val_end | double | типичные значения в начале, середине и конце процесса |
| valid_min, valid_max | double | **физические пределы** датчика: значение вне них — сбой датчика, а не процесса |
| noise_sd | double | стандартное отклонение шума; используется как допуск при сравнении с эталоном |
| norm | text | норма текстом: «~143; рано плато — катализатор» |

### 6.2. Партии

#### `batch` — партия (из дампа; колонка `quality_unit` добавляется `init_db`)

| Колонка | Тип | Описание |
|---|---|---|
| id | bigint, PK, serial | |
| formula_id | bigint, NOT NULL, FK → formula.id `ON UPDATE CASCADE ON DELETE RESTRICT` | |
| status | varchar(16), NOT NULL, default `created` | `created` / `running` / `finished` / `aborted` |
| started_at | timestamptz | момент старта |
| finished_at | timestamptz | конец процесса (конец последнего шага) |
| v_in | jsonb | сырьё по компонентам: `{"CaO": 62.5, "H20": 240}` |
| v_finish | numeric(14,4) | выход |
| quality | numeric(12,4) | качество |
| quality_unit | varchar(16) | `%` или единица концентрации |
| is_reference | boolean, NOT NULL, default false | эталонная партия |
| current_step | integer | текущий шаг; NULL — шаг не идёт |
| t_total_sec | time | длительность цикла (тип `time` — не больше суток) |

Ограничения:
- `batch_status_check` — статус из списка;
- `chk_batch_dates` — `finished_at >= started_at`;
- `chk_batch_status_dates` — `created`: обе даты NULL; `running`: есть `started_at`, нет `finished_at`;
  `finished`/`aborted`: есть обе.

Индексы: `idx_batch_formula_id`, `idx_batch_status`, `idx_batch_started_at` (DESC),
`idx_batch_reference` (частичный, `WHERE is_reference`).

#### `batch_step_window` — средние за окна (из дампа; `n_samples` добавляется `init_db`)

| Колонка | Тип | Описание |
|---|---|---|
| batch_id | bigint, NOT NULL, FK → batch.id `ON UPDATE CASCADE ON DELETE CASCADE` | |
| step | integer, NOT NULL, `>= 0` | номер шага |
| time | interval, NOT NULL, `> 0` | правая граница окна **от начала шага**: `00:00:02`, `00:00:04`, … |
| detectors | jsonb, NOT NULL, default `{}`, обязательно объект | средние по датчикам: `{"D-LAC-04": 20.1, "M-GLU-WT": 298.8}` |
| n_samples | integer | сколько показаний попало в средние (по всем датчикам окна) |

PK `(batch_id, step, time)`. Индексы: `idx_bsw_batch`, `idx_bsw_batch_step`, `idx_bsw_v_gin` (GIN по `detectors`).

#### `batch_step` — таймер шагов (создаётся `create_all`)

| Колонка | Тип | Описание |
|---|---|---|
| batch_id | bigint, NOT NULL, FK → batch.id `ON DELETE CASCADE` | |
| step | integer, NOT NULL | |
| started_at | timestamptz, NOT NULL | от этого момента отсчитывается время показаний шага |
| finished_at | timestamptz | |
| status | varchar(16), NOT NULL | `running` / `done` / `aborted` |
| planned_seconds | double | плановая длительность из `formula_steps.amount_time` |
| ended_by | varchar(16) | `timer` / `operator` / `finish` / `abort` |

PK `(batch_id, step)`.

#### `batch_recommendations` — рекомендации (создаётся `create_all`)

| Колонка | Тип | Описание |
|---|---|---|
| id | bigint, PK | |
| batch_id | bigint, NOT NULL, FK → batch.id `ON DELETE CASCADE`, индекс | |
| step | integer, NOT NULL | |
| time | interval, NOT NULL | окно, на котором замечено отклонение |
| tag | varchar, NOT NULL | датчик |
| value | double, NOT NULL | среднее за окно |
| ref_avg, ref_std | double, NOT NULL | среднее и разброс эталонов в этот момент |
| n_refs | integer, NOT NULL | сколько эталонных значений участвовало |
| delta | double, NOT NULL | `value − ref_avg` |
| threshold | double, NOT NULL | `max(k · ref_std, noise_sd)` |
| message | text, NOT NULL | текст рекомендации |
| created_at | timestamptz, NOT NULL, default now() | |

### 6.3. Симуляция (создаются `create_all`)

#### `reference_batch_values` — синтетические эталоны для симуляции

| Колонка | Тип | Описание |
|---|---|---|
| id | integer, PK | |
| formula_step_id | integer, NOT NULL, FK → formula_steps.id `ON DELETE CASCADE`, индекс | |
| batch_no | integer, NOT NULL | номер синтетической партии |
| tag | varchar, NOT NULL | |
| v_start, v_end | double, NOT NULL | значение датчика в начале и в конце стадии |

`UNIQUE (formula_step_id, batch_no, tag)`. Не связана с `batch` — это отдельный механизм симуляции.

#### `sim_runs` — прогоны

| Колонка | Тип | Описание |
|---|---|---|
| id | integer, PK | |
| formula_id | integer, NOT NULL, FK → formula.id `ON DELETE CASCADE`, индекс | |
| status | varchar(20) | `running` / `finished` / `stopped` / `failed` |
| tick_seconds | double, NOT NULL | период опроса датчиков |
| source_mode | varchar(20) | `auto` / `file` / `synthetic` |
| started_at, finished_at | timestamptz | |
| note | text | причина падения, если `failed` |

#### `sim_step_runs` — стадии прогона

| Колонка | Тип | Описание |
|---|---|---|
| id | integer, PK | |
| run_id | FK → sim_runs.id `CASCADE`, индекс | |
| formula_step_id | FK → formula_steps.id `SET NULL` | |
| step, step_key | | номер и ключ стадии |
| duration_seconds | double | длительность в этом прогоне |
| ticks | integer | сколько тиков |
| sources | text | откуда данные: `F-TT-01=file, F-pH-02=synthetic` |
| status | varchar(20) | `running` / `done` / `aborted` |
| started_at, finished_at | timestamptz | |

#### `sensor_readings` — каждое показание прогона

| Колонка | Тип | Описание |
|---|---|---|
| id | bigint, PK | |
| run_id | FK → sim_runs.id `CASCADE` | |
| step | integer | |
| ts | timestamptz, default now() | |
| elapsed_s | double | секунды от начала стадии |
| progress | double | положение внутри стадии, 0..1 |
| tag | varchar | |
| sensor_id | FK → sensors.id `SET NULL` | |
| value | double | число или NULL, если пришёл мусор |
| raw_value | varchar | как пришло: `ERR`, `37.03` |
| unit, quality | varchar | из источника |
| source | varchar(12) | `file` / `synthetic` |
| source_row_id | integer | `row_id` строки CSV |
| expected | double | эталонное значение в этот момент |
| band_min, band_max | double | допустимая полоса в этот момент |
| status | varchar(16) | `ok` / `low` / `high` / `bad_value` / `unit_error` / `sensor_fault` / `no_limits` |
| label_anomaly, label_type | boolean, varchar | разметка аномалий из CSV — для проверки качества детектора |

Индексы `(run_id, step, id)` и `(run_id, tag, id)`.

#### `sensor_alerts` — сигналы прогона

| Колонка | Тип | Описание |
|---|---|---|
| id | bigint, PK | |
| run_id | FK → sim_runs.id `CASCADE`, индекс | |
| reading_id | FK → sensor_readings.id `CASCADE` | показание, вызвавшее сигнал |
| step, ts, tag | | |
| kind | varchar(16) | `low` / `high` / `bad_value` / `sensor_fault` / `unit_error` |
| value, target | double | значение и рекомендуемое значение |
| message | text | «Нужно повысить температуру до 39 °C на датчике F-TT-01!» |

### 6.4. Как создаются таблицы

| Что | Кто создаёт |
|---|---|
| `formula`, `formula_steps`, `instruments`, `sensors`, `batch`, `batch_step_window` и их данные | дамп `sql/case_in.sql` (при первом старте Postgres) |
| `batch_step`, `batch_recommendations`, все таблицы симуляции | `init_db()` → `Base.metadata.create_all` при старте бэкенда |
| `batch.quality_unit`, `batch_step_window.n_samples` | `init_db()` → `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (только PostgreSQL) |

`create_all` создаёт только **отсутствующие** таблицы и существующие не меняет; всё идемпотентно —
перезапуск бэкенда ничего не ломает. Миграций (Alembic) в проекте нет.

---

## 7. Данные в дампе

### Формулы

| id | Название | Версия | Шагов | Длительности шагов | Комментарий |
|---|---|---|---|---|---|
| 10 | Молочная кислота | 1 | 3 | 45 мин / 1 день / 3 ч | `heat_fermenter`, `fermentation`, `isolation` |
| 11 | Молочная кислота | 2 | 3 | 45 мин / 1 день / 3 ч | вторая версия той же формулы |
| 12 | Этанол (спиртовое брожение) | 1 | 3 | 1 ч / 3 дня / 6 ч | `mash`, `fermentation`, `distillation` |
| 14 | Лактат кальция и гипс | 1 | 2 | 50 мин / 1.5 ч | |
| **15** | **Мел** | 1 | 3 | **10 с / 10 с / 10 с** | **рабочая формула**: под неё эталоны и файл эмулятора |

Формула 15:

| Шаг | step_key → step_value | Датчики |
|---|---|---|
| 1 | `CaO + H20` → `Ca(OH)2` | D-LAC-04, M-GLU-WT, P-H2O-03, A-GYPS-05 |
| 2 | `Ca(OH)2 + CO2` → `CaCO3 + H20` | C-FT-03, CI-FT-01, M-H2O-FT |
| 3 | `CaCO3` → `CaCO3` | F-PT-04, M-STER-PT |

У всех шагов `constant = {"base_errror": 0.99999}`.

### Партии

10 эталонных партий (id 1–10) формулы 15: `status = finished`, `is_reference = true`, `quality = 94`,
`t_total_sec = 00:00:30`, разное сырьё (`CaO` 60–70, `H20` 230–269). У каждой — окна на 2, 4, 6, 8, 10 с
на каждом из трёх шагов (150 строк `batch_step_window`).

### Датчики и приборы

57 датчиков, 31 прибор. Префикс тега — стадия процесса (по данным `sensor_data_5000.csv`):

| Префикс | Стадия | Датчиков |
|---|---|---|
| M | приготовление среды (`01_medium_prep`) | 5 |
| F | ферментация (`02_fermentation`, `11_finish`) | 12 |
| C | центрифуга (`03_centrifuge`) | 4 |
| A | кислотная фильтрация (`04_acid_filter`) | 5 |
| CI | уголь / ионный обмен (`05_carbon_ion`) | 5 |
| E | выпарка (`06_evaporation`) | 4 |
| P | поликонденсация (`07_polycondensation`) | 5 |
| D | деполимеризация (`08_depolymerization`) | 5 |
| L | очистка лактида (`09_lactide_purification`) | 6 |
| R | полимеризация (`10_polymerization`) | 6 |

Средняя часть тега — величина по ISA-5.1: `TT` — температура, `PT` — давление, `FT` — расход,
`pH`, `WT` — масса и т. д.

---

## 8. Формулы и расчёт массы продукта

### Создание формулы — `POST /api/formulas`

```json
{
  "name": "Лактат кальция и гипс",
  "version": 1,
  "steps": [
    {
      "step": 1,
      "step_key": "2C3H6O3 + CaCO3 -> Ca(C3H5O3)2 + H2O + CO2",
      "step_value": "Ca(C3H5O3)2",
      "in_data": {"C3H6O3": 123.0, "CaCO3": 30.0},
      "out_data": {"Ca(C3H5O3)2": 64.0},
      "constant": {"conversion": 0.98},
      "amount_time": 50,
      "dict_PLC_id": {"F-TT-01": {"pre": {"min": 35, "max": 40}, "post": {"min": 30, "max": 42}}}
    }
  ]
}
```

Проверки (ошибка → `422`, дубликат `name`+`version` → `409`):

| Поле | Правило |
|---|---|
| steps | хотя бы один; номера `step` и ключи `step_key` уникальны |
| step | `>= 1` |
| in_data | массы `> 0` |
| out_data | массы `>= 0` |
| constant | ключ латиницей (`^[A-Za-z][A-Za-z0-9_]*$`), значение `> 0` |
| amount_time | **в минутах**, `> 0`; хранится как `interval` |
| dict_PLC_id | каждый тег есть в `sensors`; каждая граница в пределах `valid_min` / `valid_max` датчика; `min <= max` |

Готовый пример — `frontend/public/formulas.json` (страница «Приёмка формул» загружает его кнопкой).

### Расчёт — `POST /api/formulas/{id}/calculate` (`app/calc.py`)

Для каждого шага по порядку:

1. `step_key` разбирается как уравнение (`->`, `-->`, `→` или `=`), **проверяется баланс атомов**;
   несбалансированное уравнение — ошибка `422`. Гидраты пишутся через `*` или `·`: `CaSO4*2H2O`.
2. Массы реагентов: из `in_data`; если реагент — продукт предыдущего шага, берётся **рассчитанная** масса
   (так шаги соединяются в цепочку; побочные продукты дальше не передаются).
3. Лимитирующий реагент = минимум `кмоль / коэффициент`; по нему — **теоретические** массы продуктов.
   Непрореагировавший избыток остальных реагентов — в `unreacted_kg`.
4. **Практическая масса** = теоретическая × **произведение всех значений `constant`** шага.
   Имена ключей ни на что не влияют — любое значение считается множителем к массе.
   Если произведение больше 1 — предупреждение в `warnings`.
5. Сравнение с ожиданием `out_data[step_value]`: отклонение в процентах и качество
   `max(0, 1 − |отклонение| / tolerance_pct)`.

Параметры запроса:

| Поле | По умолчанию | Смысл |
|---|---|---|
| inputs | — | подмена масс реагентов **первого** шага: `{"CaO": 70}` |
| constants | — | подмена констант по имени во всех шагах: `{"conversion": 0.9}` |
| spread_pct | 0 | `> 0` — диапазон итоговой массы при сдвиге всех констант на ±N % (0–50) |
| tolerance_pct | 10 | допуск для оценки качества (0–100] |

Ответ: `final_product`, `final_mass_kg`, `final_theoretical_kg`, `total_yield_pct`, `quality`
(минимум по шагам), `warnings`, `final_mass_range_kg` (если `spread_pct > 0`) и подробности по каждому шагу.
Молярные массы — по встроенной таблице атомных масс (`ATOMIC` в `calc.py`).

---

## 9. Партии: от выбора формулы до завершения

```
Оператор выбирает формулу ─► POST /api/batches                   batch.status = created
Вводит сырьё (v_in)       ─► PUT  /api/batches/{id}/v_in          (можно сразу в POST)
Нажимает «Старт»          ─► POST /api/batches/{id}/start         status = running, started_at = now
                                                                  batch_step(шаг 1).started_at = now
  ┌── каждый тик (0.1 с) ──────────────────────────────────────────────────────────┐
  │ берём из txt строки, «пришедшие» к этому моменту (эмулятор OPC)                │
  │ t = время строки − начало текущего шага                                        │
  │ показание датчика этого шага → в буфер окна                                    │
  │ окно закрылось → средние → batch_step_window (time = правая граница окна)      │
  │                 сравнение с эталоном → batch_recommendations                   │
  │ время шага вышло (formula_steps.amount_time) → следующий шаг, его started_at   │
  └────────────────────────────────────────────────────────────────────────────────┘
Все шаги пройдены          ─► current_step = NULL                 phase = awaiting_finish
Вводит выход и качество    ─► POST /api/batches/{id}/finish       status = finished,
                                                                  finished_at, t_total_sec, is_reference
```

### Что проверяется при старте

| Условие | Ошибка |
|---|---|
| партия в статусе `created` | `409` |
| `v_in` введено | `422` |
| файл эмулятора существует, лежит в `data/` и разбирается | `422` |
| у формулы есть шаги | `422` |
| все теги из `dict_plc_id` есть в `sensors` | `422` со списком тегов |

Затем загружаются эталонные партии (раздел 12), и стартует фоновая задача `BatchSession`.

### Статусы и фазы

`batch.status` хранится в БД. API дополнительно отдаёт вычисляемое поле `phase`:

| status | phase | Смысл | Пульт |
|---|---|---|---|
| created | created | создана, можно вводить `v_in` | создана |
| running | running | идёт шаг `current_step` | идёт |
| running | awaiting_finish | все шаги пройдены, ждём выход и качество | ждёт итога |
| finished | finished | закрыта; может быть эталонной | завершена |
| aborted | aborted | прервана оператором | прервана |

### Действия оператора во время партии

| Действие | Эндпоинт | Что происходит |
|---|---|---|
| Закончить шаг досрочно | `POST /{id}/next-step` | текущее окно закрывается с фактической границей (например, `3.239 с`), шаг `ended_by = operator`, сразу стартует следующий |
| Завершить | `POST /{id}/finish` | можно и посреди шага: шаг закрывается с `ended_by = finish` |
| Прервать | `POST /{id}/abort` | шаг `status = aborted`, партия `aborted` |
| Пометить эталоном | `PUT /{id}/reference` | только для `finished`; снять отметку можно всегда |

Шаг без `amount_time` по таймеру не заканчивается — только кнопкой оператора.

### Время

- **Время показаний всегда считается от начала шага**, а не по часам сервера — поэтому партии,
  запущенные в разное время, сравнимы между собой.
- `batch_step.started_at` / `finished_at` — реальные моменты (UTC).
- `batch.finished_at` — **конец процесса** (конец последнего шага), а не момент нажатия «Завершить»:
  пауза оператора перед вводом качества не попадает в `t_total_sec`.
- `speed` ускоряет и файл эмулятора, и таймеры шагов одинаково. Реальные отметки времени при этом
  реальные: при `speed = 10` 30-секундная партия длится 3 с, и `t_total_sec = 3`.

### Живой статус — `GET /api/batches/{id}` → `live`

Есть, пока партия обрабатывается этим процессом бэкенда (иначе `null`):

| Поле | Смысл |
|---|---|
| receiving | идёт ли приём показаний |
| process_time_s | секунды процесса от старта (с учётом `speed`) |
| step, step_elapsed_s, step_planned_s | текущий шаг, сколько прошло, план |
| steps_done | все шаги пройдены |
| speed, window_s | параметры старта |
| reference_batches | id эталонных партий, с которыми идёт сравнение |
| opc.read / opc.total | сколько строк файла прочитано из скольких |
| readings | счётчики: `accepted`, `ignored`, `bad_value`, `out_of_range` (раздел 11) |
| last_windows | последние 5 окон со средними |
| recommendations | последние 20 рекомендаций |
| error | текст ошибки, если обработка упала |

---

## 10. Эмулятор OPC (txt-файл с показаниями)

В MVP показания читаются не с OPC-сервера, а из txt-файла (`app/batches/opc.py`). Одна строка — одно показание:

```
# эмулятор OPC: формула 15, эталонные партии [...]
# start=2026-10-20T10:00:00
# время;датчик;значение
2026-10-20T10:00:00.5;D-LAC-04;19.9251
2026-10-20T10:00:01;D-LAC-04;19.9381
2026-10-20T10:00:01;P-H2O-03;ERR
```

| Правило | Подробно |
|---|---|
| Комментарии | строки с `#` пропускаются; пустые — тоже |
| `# start=...` | момент старта партии в шкале файла; без него стартом считается первая строка |
| Время | ISO 8601, дробная часть любой длины: `10:00:00.5`, `10:00:01` |
| Проигрывание | файл стартует вместе с партией; строка «приходит», когда с начала прошло столько же секунд, сколько между ней и `start` |
| Порядок | строки сортируются по времени (стабильно) |
| Мусор | нечисловое значение (`ERR`, пусто) не ломает партию — попадает в счётчик `bad_value` |
| Ошибки | строка не из трёх полей или неразбираемое время — `422` при старте с номером строки |
| Расположение | по умолчанию `data/opc_formula15.txt` (переменная `OPC_FILE`); в запросе старта можно указать `opc_file` — только файл из `data/` |

### Генератор файла — `scripts/make_opc_file.py`

```bash
python scripts/make_opc_file.py                 # формула 15 → data/opc_formula15.txt
python scripts/make_opc_file.py --clean         # без намеренных отклонений и строки ERR
python scripts/make_opc_file.py --formula 15 --interval 0.5 --window 2 --seed 15 --out data/x.txt
```

Читает эталонные партии **прямо из `sql/case_in.sql`** (БД не нужна). Для каждого шага и окна эталонов:
значение = среднее эталонов + гауссов шум (`noise_sd / 2`), обрезанное по `valid_min` / `valid_max`;
показание каждые `--interval` с. Шаги идут друг за другом, длительность шага — последнее окно эталона.

Намеренные отклонения — список `DEVIATIONS` в начале скрипта:

| Шаг | Датчик | Окно | Множитель | Ожидаемая рекомендация |
|---|---|---|---|---|
| 1 | D-LAC-04 | 6 с | ×0.80 | увеличить массу лактида |
| 2 | CI-FT-01 | 8 с | ×1.45 | уменьшить расход |

Плюс одна строка `ERR` у `P-H2O-03` на 1-й секунде. Готовый файл: 181 показание, 30 секунд.

---

## 11. Усреднение по окнам

Реализация — `app/batches/process.py` (`BatchProcess`).

- Окно — полуинтервал **(end − window; end]**: показание ровно на 2.0 с попадает в окно `time = 2.0`.
- Размер окна — `window_seconds` при старте, по умолчанию **2 с** (4 показания × 0.5 с, как в ТЗ и в эталонах).
- Окно закрывается, когда время шага ушло за его правую границу. Пустые окна не записываются.
- Последнее окно обрезается концом шага; если шаг закончил оператор, `time` — фактическая граница.
- Одна строка `batch_step_window` на окно, в `detectors` — средние **всех** датчиков шага.

**В средние не попадают** (и считаются в `live.readings`):

| Счётчик | Причина |
|---|---|
| `ignored` | датчика нет в `dict_plc_id` текущего шага, или шаг не идёт |
| `bad_value` | нечисловое значение |
| `out_of_range` | значение вне `sensors.valid_min / valid_max` — сбой датчика, а не процесса |
| `accepted` | попало в среднее |

---

## 12. Сравнение с эталоном и рекомендации

### Выбор эталонов (при старте партии, `repo.load_references`)

1. **Кандидаты** — партии той же формулы с `is_reference = true` и `status = finished`, кроме самой партии;
   до 100 последних по `started_at` (`REF_POOL`); опционально только с `quality >= min_ref_quality`.
2. **Выбор** `ref_limit` (по умолчанию 10) — сначала **ближайшие по `v_in`**, при равенстве — более свежие.
   Расстояние — средняя относительная разница по компонентам сырья:
   `|a − b| / max(|a|, |b|)`, не больше 1; компонент есть только у одной партии → 1.
3. Окна выбранных партий загружаются в память один раз на всю партию.

### Проверка каждого закрытого окна (`reference.compare`)

```
значения эталонов на этом шаге и в это же время окна  →  ref_avg, ref_std (выборочное)
delta     = текущее среднее − ref_avg
threshold = max(k · ref_std, noise_sd датчика)          k = 3 по умолчанию
|delta| > threshold  →  рекомендация
```

- Если у эталонов нет окна на это время (шаг закончен досрочно, окно другой длины) — окно не сравнивается.
- Текст строит `monitoring.engine.action_message`: глагол по знаку `delta` — «повысить/понизить» для
  температуры, давления, pH, вакуума, оборотов и т. п., «увеличить/уменьшить» для остального;
  параметр — первое слово `sensors.parameter` в винительном падеже; целевое значение — `ref_avg`.
- Рекомендация пишется в `batch_recommendations`, в лог бэкенда (уровень WARNING) и в `live.recommendations`.

> ⚠️ **Качество эталонов решает всё.** Партия с аномалией, помеченная эталонной, раздувает `ref_std`,
> и порог перестаёт ловить отклонения (проверено: одна такая партия «глушит» обе рекомендации формулы 15).
> Помечайте эталонными только действительно хорошие партии.

---

## 13. Симуляция стадий (модуль monitoring)

Более ранний и **независимый** от партий механизм: прогон формулы по стадиям с проверкой **каждого**
показания по допустимым диапазонам `dict_plc_id` и синтетическим эталонам. Пишет в свои таблицы
(раздел 6.3). Одновременно может идти только один прогон.

### Как работает

1. **Эталоны.** Для каждой пары (стадия, датчик) берётся «идеальное» начало и конец — центр допустимой
   полосы в начале и в конце стадии, а если диапазонов нет — `val_start` / `val_end` датчика.
   Генерируется N синтетических партий (по умолчанию 30) с разбросом (8 % ширины полосы или шум датчика)
   → `reference_batch_values`. Средние по ним — эталонная кривая (прямая от начала к концу).
   Если эталонов для стадии нет, они генерируются автоматически при старте.
2. **Полоса допуска** в момент `p` (0 — начало стадии, 1 — конец): есть `during` — действует всю стадию;
   есть `pre` и `post` — плавно переходит от `pre` к `post`; есть одна — она; нет ничего — эталон
   ± `max(4·noise_sd, 3 %)`.
3. **Длительность стадии** (приоритет): `step_durations[номер]` → `step_seconds` → `amount_time` из БД.
   Если `amount_time` больше 120 с (например, «1 day»), прогон не запустится — укажите `step_seconds`.
4. **Источник показаний** для каждого датчика:
   - `synthetic` — генератор: эталон + шум, с вероятностью `fault_rate` — выход за полосу или `ERR`;
   - `file` — строки `data/sensor_data_5000.csv` этого датчика, равномерно распределённые по тикам стадии;
   - `auto` — файл, если ≥ 70 % его значений ложатся в полосу этой стадии (иначе файл про другую стадию), иначе генератор.
5. **Проверка показания** → статус:

| Статус | Когда |
|---|---|
| `ok` | в полосе |
| `low` / `high` | ниже / выше полосы → сигнал «Нужно повысить/понизить … до …» |
| `bad_value` | не число |
| `unit_error` | единица из источника не совпала с единицей датчика |
| `sensor_fault` | вне физических пределов датчика |
| `no_limits` | полосу не определить |

Всё, кроме `ok` и `no_limits`, — сигнал (`sensor_alerts`).

### Формат `sensor_data_5000.csv`

`row_id, timestamp, batch_id, stage, tag, instrument_id, value, unit, quality, progress_pct, is_anomaly, anomaly_type` —
5000 строк одной партии `PLA-2026-10-001`, 57 датчиков, 11 стадий. `quality`: GOOD / BAD / UNCERTAIN.
Разметка аномалий (`is_anomaly`, `anomaly_type`: spike, drift, stuck, dropout_zero, missing, error_string,
noise_burst, unit_error, out_of_range, ts_duplicate, ts_backward, process_violation) нужна, чтобы проверять
качество детектора: тест модуля печатает «найдено / пропущено / ложных тревог».

---

## 14. Фронтенд (пульт оператора)

SPA на React Router 8 в режиме `ssr: false`: собирается статика `frontend/build/client`, её отдаёт nginx.
Все запросы — по относительным путям `/api/...`: в разработке их проксирует Vite, в контейнере — nginx.

### Страницы

| Маршрут | Файл | Что показывает | API | Обновление |
|---|---|---|---|---|
| `/` | `dashboard.tsx` | сводка: текущая партия (мнемосхема стадий), установка, статистика партий, симуляция | `/api/batches`, `/api/sensors`, `/api/formulas`, `/api/simulation/status` | опрос |
| `/sensors` | `sensors.tsx` | паспорта датчиков: тег, параметр, единица, прибор, пределы; поиск; состав по параметрам | `/api/sensors` | при открытии |
| `/formulas` | `formulas.tsx` | список формул, карточки стадий (массы, константы, датчики с диапазонами), форма расчёта выхода | `/api/formulas`, `/{id}`, `/{id}/calculate` | при открытии; по умолчанию формула 15 |
| `/formulas/import` | `formulas-import.tsx` | приёмка формул из JSON: локальная проверка (зеркало серверных правил) → отправка | `POST /api/formulas`, `/api/sensors` | — |
| `/batches` | `batches.tsx` | журнал партий + форма «формула → сырьё → ускорение (×1, 5, 10, 30, 60) → старт» | `/api/batches`, `POST /api/batches`, `/start` | каждые 5 с |
| `/batches/:id` | `batch-detail.tsx` | ведение партии: стадии, график средних по окнам, таблица окон, рекомендации, кнопки «досрочно» / «прервать», завершение | `/api/batches/{id}`, `/metrics`, `/recommendations`, `/next-step`, `/finish`, `/abort` | каждые 1.5 с |
| `/simulation` | `simulation.tsx` | запуск прогона, живой статус, сигналы, эталонные полосы, журнал прогонов | `/api/simulation/*` | статус 1 с, журнал 5 с |
| `/demo` | `demo.tsx` | диаграммы симуляции по стадиям: цвет на датчик, полоса нормы, шкала отклонения | `/api/simulation/start`, `/stop`, `/status`, `/runs/{id}/readings` | 0.8–0.9 с |
| `/about` | `about.tsx` | справка: как работает система, разделы, обозначения | — | — |
| `*` | `not-found.tsx` | 404 | — | — |

### Общие модули

| Файл | Что внутри |
|---|---|
| `lib/api.ts` | типы ответов (один в один с `app/routers/*.py`) и функции для каждого эндпоинта; `ApiError` + `formatDetail` превращают `detail` FastAPI (включая ошибки pydantic) в читаемый текст |
| `lib/usePoll.ts` | хук опроса: не накладывает запросы, ставится на паузу, когда вкладка скрыта |
| `lib/format.ts` | подписи фаз (`phaseLabel`), цвета статусов, форматирование чисел, времени, длительностей, химических формул с индексами (`chemText`) |
| `components/ui.tsx` | `PageHead`, `Panel`, `Chip`, `Notice`, `Spinner`, `Empty`, `TableScroll`, `StatBlock` |
| `components/chart.tsx` | `SeriesChart` (линейный график на SVG, несколько серий, полосы) и `Sparkline` |
| `app.css` | палитра (`@theme`): стальные нейтральные, «реагентный» сине-зелёный, янтарь и киноварь для тревог; компоненты (`btn`, `tagplate`, `readout`, …) |

Оформление — светлый «приборный пульт» по мотивам ISA-101; шрифты IBM Plex Sans / Mono (Google Fonts).

### Сборка в Docker

`frontend/Dockerfile`: этап `node:24-alpine` ставит зависимости (`bun install --frozen-lockfile`, если есть
`bun.lock`, иначе `npm ci`) и собирает; этап `nginx:1.27-alpine` раздаёт `build/client` с `nginx.conf`:
`/api/*` и `/docs|/redoc|/openapi.json` → `http://backend:8000` (таймаут 300 с), остальные пути → `index.html`,
`/assets/` кэшируется на 7 дней, `index.html` — без кэша, gzip включён.

### Старый фронтенд — `frontend-old/`

Прежние статические страницы `formulas.html` и `batches.html` (+ `js/`, `data/formulas.json`). Оставлены
для истории; бэкенд их **не раздаёт** (раздел 20).

---

## 15. API — полный справочник

Все ответы — JSON. Ошибки: `404` — не найдено, `409` — действие не подходит к состоянию, `422` — неверные
данные (текст в `detail`). Интерактивно — http://localhost:8000/docs.

### Датчики — `/api/sensors`

| Метод | Путь | Ответ |
|---|---|---|
| GET | `/api/sensors` | `[{id, tag, parameter, unit, instrument, valid_min, valid_max}]`, по тегу |

### Формулы — `/api/formulas`

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| POST | `/api/formulas` | формула (раздел 8) | `{id, name, version, steps_count}` |
| GET | `/api/formulas` | | `[{id, name, version, created_at}]` |
| GET | `/api/formulas/{id}` | | формула со шагами; `amount_time_min`; `sensors: {tag: {limits, parameter, unit}}` |
| POST | `/api/formulas/{id}/calculate` | `{inputs?, constants?, spread_pct?, tolerance_pct?}` | расчёт массы (раздел 8) |

### Партии — `/api/batches`

| Метод | Путь | Тело / параметры | Что делает |
|---|---|---|---|
| POST | `/api/batches` | `{"formula_id": 15, "v_in": {...}?}` | создать (`created`) |
| GET | `/api/batches` | `?formula_id=15&only_reference=true` | последние 100 партий |
| GET | `/api/batches/{id}` | | партия + `steps` + `recommendations_total` + `live` |
| PUT | `/api/batches/{id}/v_in` | `{"v_in": {"CaO": 62.5, "H20": 240}}` | сырьё (только `created`, значения `> 0`) |
| POST | `/api/batches/{id}/start` | параметры ниже | старт |
| POST | `/api/batches/{id}/next-step` | | досрочно закончить текущий шаг |
| POST | `/api/batches/{id}/finish` | `{"v_finish": 100.5, "quality": 94, "quality_unit": "%", "is_reference": false}` | завершить |
| POST | `/api/batches/{id}/abort` | | прервать |
| PUT | `/api/batches/{id}/reference` | `{"is_reference": true}` | эталонная (ставить — только `finished`) |
| GET | `/api/batches/{id}/metrics` | `?step=1` | `[{step, time_s, V, n_samples}]` |
| GET | `/api/batches/{id}/recommendations` | `?step=1&after_id=0` | `[{id, step, time_s, tag, value, ref_avg, ref_std, n_refs, delta, threshold, message}]`, до 1000; `after_id` — только новые |

Параметры старта (все необязательные):

| Поле | По умолчанию | Диапазон | Смысл |
|---|---|---|---|
| speed | 1 | (0; 100] | ускорение времени |
| window_seconds | 2 | (0; 3600] | окно усреднения |
| k | 3 | (0; 20] | множитель разброса в пороге |
| ref_limit | 10 | 1–100 | сколько эталонных партий сравнивать |
| min_ref_quality | — | | эталоны только с `quality >=` |
| opc_file | `opc_formula15.txt` | | файл показаний из `data/` |

Поля партии в ответах: `id, formula_id, status, phase, v_in, started_at, finished_at, current_step,
t_total_sec` (секунды), `v_finish, quality, quality_unit, is_reference`.

### Симуляция — `/api/simulation`

| Метод | Путь | Тело / параметры | Что делает |
|---|---|---|---|
| POST | `/reference/generate` | `{formula_id, n_batches: 30, seed?}` | пересоздать синтетические эталоны всех стадий |
| GET | `/reference/{fid}` | | по стадиям: полосы начала и конца, средние эталонов, число партий |
| PATCH | `/formulas/{fid}/steps/{step}/duration` | `{"seconds": 14}` | записать `amount_time` стадии в секундах |
| POST | `/start` | параметры ниже | запустить (`409`, если уже идёт) |
| POST | `/stop` | | остановить |
| GET | `/status` | | текущий прогон: стадия, время, счётчики, последние 20 сигналов |
| GET | `/runs` | | последние 50 прогонов |
| GET | `/runs/{id}/steps` | | стадии прогона |
| GET | `/runs/{id}/readings` | `?step&tag&only_alerts&after_id&limit=200` (до 2000) | показания |
| GET | `/runs/{id}/alerts` | `?step` | сигналы |

Параметры `/start`:

| Поле | По умолчанию | Смысл |
|---|---|---|
| formula_id | — | обязательно |
| steps | все | какие стадии запустить |
| tick_seconds | 0.5 | период опроса (0.05–60) |
| step_seconds | — | длительность **всех** стадий, с |
| step_durations | `{}` | по стадиям: `{"1": 10, "2": 14}` |
| save_durations | false | записать длительности в `formula_steps.amount_time` |
| source | `auto` | `auto` / `file` / `synthetic` |
| fault_rate | 0.05 | доля сбоев в синтетике (0–1) |
| seed | — | воспроизводимость |
| reference_batches | 30 | сколько эталонов генерировать, если их нет |

### Пример: партия через curl

```bash
A=localhost:8000/api/batches; H='content-type: application/json'
curl -s -XPOST $A -H "$H" -d '{"formula_id":15,"v_in":{"CaO":62.5,"H20":240}}'   # → {"id": 11, ...}
curl -s -XPOST $A/11/start -H "$H" -d '{"speed":10}'
curl -s $A/11                     # live.step, live.step_elapsed_s, live.recommendations
curl -s $A/11/metrics
curl -s $A/11/recommendations
curl -s -XPOST $A/11/finish -H "$H" -d '{"v_finish":100.5,"quality":94}'
```

---

## 16. Настройки и переменные окружения

### Файлы

| Файл | Для чего | Содержимое |
|---|---|---|
| `.env` | локальный запуск бэкенда | `SQLALCHEMY_DATABASE_URL=...@localhost:5433/case_in`; `SECRET_KEY` (в коде сейчас не используется) |
| `.env.docker` | все контейнеры | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; `SQLALCHEMY_DATABASE_URL=...@postgres:5432/case_in`; `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD` |

### Переменные окружения

| Переменная | Где | По умолчанию |
|---|---|---|
| `SQLALCHEMY_DATABASE_URL` | бэкенд | SQLite `./database.db` |
| `OPC_FILE` | бэкенд, партии | `data/opc_formula15.txt` |
| `SENSOR_DATA_FILE` | бэкенд, симуляция | `data/sensor_data_5000.csv` |
| `BACKEND_URL` | фронтенд, dev-сервер Vite | `http://localhost:8000` |

### Константы в коде

| Где | Константа | Значение | Смысл |
|---|---|---|---|
| `app/batches/reference.py` | `REF_LIMIT` | 10 | эталонов в сравнении |
| | `K_STD` | 3.0 | множитель разброса |
| `app/batches/repo.py` | `REF_POOL` | 100 | из скольких последних эталонов выбирать |
| `app/batches/session.py` | `TICK_S` | 0.1 | период обработки показаний, с |
| `app/monitoring/plan.py` | `MAX_REAL_SECONDS` | 120 | максимум `amount_time` из БД для симуляции без явной длительности |
| `app/monitoring/source.py` | `pick_sources(threshold)` | 0.7 | доля значений файла в полосе для режима `auto` |
| `app/monitoring/manager.py` | журнал событий | 500 | последних событий в памяти |

### Порты

| Порт | Сервис | Доступен |
|---|---|---|
| 3000 | frontend (nginx) | со всех интерфейсов |
| 8000 | backend | со всех интерфейсов |
| 5433 | postgres | только `127.0.0.1` |
| 5050 | pgadmin | только `127.0.0.1` |

---

## 17. Тесты

```bash
python -m unittest discover -s tests -v
```

БД, FastAPI и зависимости не нужны — достаточно стандартного Python.

| Файл | Что проверяет |
|---|---|
| `tests/test_batches.py` | эмулятор OPC (разбор времени, `# start=`, ошибки, `poll`); окна по 4 показания и таймеры шагов; отсев чужих датчиков, мусора и выбросов; досрочный переход; шаг без длительности; расстояние по `v_in` и выбор эталонов; порог `max(k·std, допуск)`; **сквозной прогон** `data/opc_formula15.txt` с эталонами из `sql/case_in.sql`: 15 окон, ровно две рекомендации (заложенные), ни одной ложной |
| `tests/test_monitoring.py` | полосы допусков, эталонная кривая, проверка показаний, тексты сигналов, генерация эталонов, длительности, источники, цикл прогона; прогон по реальному CSV с подсчётом найденных и пропущенных аномалий |

Если меняете `sql/case_in.sql` или `DEVIATIONS` в генераторе — перегенерируйте файл эмулятора и прогоните тесты.

Фронтенд: `bun run typecheck` в `frontend/`.

---

## 18. Работа с репозиторием

Основной репозиторий — `Zloyaziat/case_in`. Если прав на пуш нет, работа идёт через форк:

```bash
git remote -v
# origin    https://github.com/<ваш-логин>/case_in.git   ← форк: сюда push
# upstream  https://github.com/Zloyaziat/case_in         ← основной: отсюда pull

git config remote.pushDefault origin          # push по умолчанию — в форк
git branch -u upstream/master                 # pull по умолчанию — из основного
git pull                                      # забрать изменения команды
git push                                      # отправить в форк → Pull Request на GitHub
```

Если `git pull` пишет «Already up to date», а изменения команды не появились — скорее всего, `pull`
смотрит в форк, а не в `upstream` (настройте, как выше). В VS Code при выборе ветки не выбирайте
`origin/master` / `upstream/master` — это снимки удалённых репозиториев, а не ваши ветки
(получится «detached HEAD»); ваша ветка — просто `master`.

---

## 19. Принятые решения

### Открытые вопросы ТЗ

| Вопрос | Решение | Где поменять |
|---|---|---|
| Окно усреднения | 2 с, общее для всех датчиков шага | `window_seconds` при старте |
| Завершение шага | по `amount_time` **или** кнопкой оператора; без `amount_time` — только оператор | `app/batches/process.py` |
| «Приоритет массы сырья» | подбор эталонов по близости `v_in`; нормировки показаний на объём нет | `reference.v_in_distance` |
| Статус эталона | вручную: флаг при завершении или `PUT /reference` | — |
| Шаги разной длины | сравниваются только окна с тем же временем | `RefIndex.at` |

### Отличия от текста ТЗ

| В ТЗ | В проекте | Почему |
|---|---|---|
| `batch_step_metrics`, поле `V` | `batch_step_window`, поле `detectors` | таблица уже была в дампе |
| `step_no` | `step` | так во всех таблицах проекта |
| `v_in` — число | `v_in` — словарь по компонентам | так в дампе |
| `device`, `formula_step.device_id`, `sensor.interval_ms` | `instruments`; датчики шага — из `dict_plc_id`; окно общее | так проект был устроен до ТЗ; у шагов формулы 15 несколько приборов |
| шаблоны текстов в БД | `action_message` в коде | общая функция с симуляцией |

---

## 20. Ограничения и известные проблемы

### Логика

- **Досрочный переход сдвигает данные.** Файл эмулятора — один поток на всю партию. Если шаг закончен
  раньше, показания следующего шага придут позже его старта, окна разойдутся с эталоном по времени
  (такие окна не сравниваются).
- **Перезапуск бэкенда.** Приём показаний живёт в памяти: после перезапуска идущие партии остаются
  `running` без `live` — их можно завершить или прервать. То же для симуляции.
- **Один воркер.** Партии и симуляция управляются из того процесса, где запущены — не запускайте uvicorn
  с `--workers > 1`.
- **`t_total_sec`** имеет тип `time` — партия дольше суток не запишется (`422`).
- **Единицы `amount_time`.** `POST /api/formulas` принимает **минуты**; партии читают интервал как есть;
  `PATCH /api/simulation/.../duration` пишет **секунды**. У формулы 15 в дампе — 10 секунд.
- **Константы формулы** — только множители к массе; названия ключей не влияют на расчёт.

### Код и репозиторий

- **Бэкенд по-прежнему раздаёт `/frontend` и редиректит `/` на `/frontend/formulas.html`** (`app/main.py`).
  После переезда старых страниц в `frontend-old/` по этим адресам ничего полезного нет (404 на редиректе,
  а `/frontend/` отдаёт исходники нового фронта). Пульт — на порту 3000.
- **В репозитории лежат 33 файла `__pycache__/*.pyc`** (Python 3.13 и 3.14). Их стоит удалить из git и
  добавить `.gitignore` с `__pycache__/`, `.venv/`, `*.pyc`.
- **`app/chemistry_steps/`** — устаревший роутер формул, нигде не подключён.
- **`frontend/README.md`** упоминает `docker/Dockerfile` и `docker/nginx.conf` — на самом деле файлы лежат
  прямо в `frontend/`.
- **Секреты в git.** `.env` и `.env.docker` закоммичены (пароли — учебные). Для реального развёртывания
  их нужно вынести из репозитория.

---

## 21. Частые проблемы

| Симптом | Причина и решение |
|---|---|
| Пусто: нет формул и датчиков | дамп не загрузился — `docker compose logs postgres`; если volume уже был, дамп не грузится: `docker compose down -v && docker compose up -d --build` |
| `port is already allocated` | порт 3000/8000/5433/5050 занят — остановите другой проект или поменяйте порт слева в `ports:` в `docker-compose.yml` |
| Пульт открывается, но «Нет связи с сервером» | бэкенд не запущен или упал — `docker compose logs backend` |
| `422: сначала введите v_in` | у партии нет сырья — введите его в форме или `PUT /v_in` |
| `422: неизвестные датчики` | в `dict_plc_id` формулы тег, которого нет в `sensors` |
| Симуляция: «стадия длится 86400 с по данным БД» | `amount_time` слишком большой — передайте `step_seconds` |
| Рекомендаций нет, хотя должны быть | эталоны «испорчены» плохой партией с `is_reference = true` (раздел 12) — снимите отметку |
| `git pull` — «Already up to date», а изменений нет | `pull` смотрит в форк — раздел 18 |
| Windows: ошибки в `.sh`/`.sql` из `sql/` | файлы с CRLF; `.gitattributes` закрепляет LF — переклонируйте или `git add --renormalize .` |
