# Пульт оператора — малотоннажная химия

SPA-фронтенд (React Router 8 + Tailwind 4, режим `ssr: false`) к FastAPI-бэкенду из `../app/`.
Заменяет старые страницы `frontend-old/` (`formulas.html`, `batches.html`): те же маршруты API,
тот же набор данных, но живой интерфейс в стиле приборного пульта.

## Разделы

| Маршрут | Что делает | API |
| --- | --- | --- |
| `/` | Сводка: текущая партия, состав установки, состояние симуляции | `/api/batches`, `/api/sensors`, `/api/formulas`, `/api/simulation/status` |
| `/sensors` | Паспорта приборов: тег, параметр, единицы, физические пределы | `/api/sensors` |
| `/formulas` | Цепочки стадий, диапазоны датчиков, расчёт выхода продукта | `/api/formulas`, `/api/formulas/{id}`, `/api/formulas/{id}/calculate` |
| `/formulas/import` | Приёмка формул из JSON: локальная валидация → отправка в БД | `/api/formulas` (POST) |
| `/batches` | Журнал партий + создание и запуск партии | `/api/batches`, `/{id}/start` |
| `/batches/:id` | Живое ведение партии: стадии, окна усреднения (график), рекомендации, завершение | `/api/batches/{id}`, `/metrics`, `/recommendations`, `/next-step`, `/finish`, `/abort` |
| `/simulation` | Прогон стадий: старт/стоп, живой статус, сигналы, эталонные полосы | `/api/simulation/*` |

## Локальная разработка

```bash
bun install          # или npm install
bun run dev          # http://localhost:3000
```

Бэкенд должен быть поднят (порт 8000):

```bash
cd .. && docker compose up postgres backend
# либо: uvicorn app.main:app --reload
```

В dev-сервер встроен прокси `/api → http://localhost:8000` (см. `vite.config.ts`),
поэтому CORS не нужен; адрес бэкенда можно переопределить переменной `BACKEND_URL`.

## Сборка и проверка типов

```bash
bun run typecheck    # react-router typegen && tsc
bun run build        # статика в build/client
```

## Docker

`docker/Dockerfile` собирает статику (`build/client`) и отдаёт её через nginx;
`docker/nginx.conf` проксирует `/api`, `/docs`, `/redoc`, `/openapi.json` на сервис `backend`
в compose-сети и маршрутизирует все остальные пути на `index.html` (SPA).

```bash
docker compose up --build frontend    # http://localhost:3000
```

## Оформление

Светлый приборный пульт (по мотивам ISA-101): стальная подложка с разлиновкой,
белые панели, единственный активный цвет — «реагентный» сине-зелёный; тревоги —
янтарь и киноварь. Теги датчиков показываются шильдиками, цифры — моноширинным
с табличными знаками. Шрифты: IBM Plex Sans / IBM Plex Mono (кириллица).
Токены палитры и компоненты — в `app/app.css` (`@theme`, `@layer components`).
