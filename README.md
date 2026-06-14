# DAIOS — Daily AI Operating System

**DAIOS** — персональная система продуктивности с AI-агентами: личный дашборд задач,
тренировок, заметок и фокуса на неделю/месяц, плюс Telegram-бот, который дважды в день
присылает сводку с контентом, подобранным под ваши интересы.

Система сама собирает контент из разных источников (RSS, YouTube, VK, NewsAPI), с помощью
LLM генерирует поисковые запросы под ваш текущий фокус и формирует утреннюю и вечернюю
сводки.

---

## Возможности

- 📋 **Задачи и бэклог** — дневные задачи со статусами, отложенные задачи с причинами.
- 🎯 **Фокус недели/месяца** — задаёте приоритет, под который подстраивается весь контент.
- 🏋️ **Тренировки** — план тренировок (с импортом из Google Sheets), длительность и статус.
- 📝 **Заметки** и **календарь**.
- 🤖 **AI-агенты на LangGraph** — оркестратор последовательно запускает агентов
  (контент, задачи, тренировки, контекст, вечерняя сводка).
- 📰 **LLM-контентный пайплайн** — динамический сбор ссылок под фокус пользователя,
  выбор лучших через LLM, деление на утро/вечер.
- 📨 **Telegram-бот** — утренняя и вечерняя сводки, отдельный лог-бот для алертов об ошибках.
- ⏰ **Планировщик (APScheduler)** — крон-задачи сбора контента и рассылки сводок.
- 🔐 **JWT-авторизация**.

---

### Backend (Python 3.12+)

| Компонент | Технология |
|---|---|
| Web / API | **Litestar** |
| AI-агенты | **LangGraph** + LangChain |
| LLM | **OpenRouter** (через `langchain-openai`) |
| БД | **PostgreSQL** + SQLAlchemy (async, asyncpg) |
| Миграции | **Alembic** |
| Кэш / очередь | **Redis / Valkey** |
| Telegram | **Aiogram 3** |
| Планировщик | **APScheduler** |
| DI-контейнер | **Dishka** |
| Конфиг / валидация | **Pydantic** + pydantic-settings |

Структура `backend/`:

```
api/            — контроллеры Litestar (tasks, backlog, focus, workouts, notes, settings, debug)
agents/         — LangGraph-агенты + оркестратор
services/       — бизнес-логика (content, focus, task, workout, llm, wakeup_planner, ...)
integrations/   — внешние источники (rss, youtube, vk, news, weather, google_sheets, ...)
repositories/   — доступ к данным
models/         — SQLAlchemy-модели
bot/            — Telegram-бот (handlers, keyboards, middlewares)
logbot/         — отдельный бот для алертов об ошибках
scheduler/      — крон-задачи (jobs.py)
core/           — config, db, redis, providers (DI), logging, middleware
auth/           — JWT-авторизация
migrations/     — Alembic
```

Сервисы запускаются как отдельные контейнеры: **api**, **bot**, **scheduler**, **logbot**.

### Frontend

| Компонент | Технология |
|---|---|
| Рантайм | **Bun** |
| Сервер | **Hono** |
| Стили | **Tailwind CSS v4** |
| Язык | **TypeScript** |

Структура `frontend/src/`:

```
routes/      — страницы: today, backlog, workouts, focus, notes, calendar, settings, auth
components/  — table, card
layouts/     — base (сайдбар + мобильный header), auth
style.css    — исходник Tailwind v4
```

> ⚠️ `public/style.css` — **скомпилированный** файл, который раздаётся сервером.
> После каждого изменения `src/style.css` нужно пересобрать CSS:
> ```bash
> cd frontend && bunx tailwindcss -i src/style.css -o public/style.css
> ```

### Инфраструктура

- **Nginx** как reverse proxy (работает на сервере по 443 порту).
- Docker Compose разбит на файлы: `infra` (PostgreSQL + Redis), `backend`, `frontend`, `nginx`.

---

## Контентный пайплайн

**Этап 1 — Сбор** (крон `collect_content`):
статический сбор (RSS / YouTube / VK / NewsAPI) → `FocusResolver` определяет фокус
(неделя → месяц → интересы) → LLM генерирует поисковые запросы → динамический сбор → БД.

**Этап 2 — Сводка** (крон `morning_brief` / `evening_brief`):
`FocusResolver` → кандидаты из БД → LLM выбирает лучшие ссылки → утро (первые 3) +
вечер (вторые 3).

**Fallback-цепочки:**
- LLM упал при сборе → используется статический контент из БД.
- LLM упал при выборке → выбор по приоритету топиков.
- Нет фокуса недели → месячный → интересы.

---

## Быстрый старт

### Требования

- Docker + Docker Compose
- (для локальной разработки) [uv](https://github.com/astral-sh/uv), Bun

### 1. Настройка окружения

```bash
cp .env.example .env
```

Заполните ключи в `.env`:

| Переменная | Где взять |
|---|---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_USER_ID` | [@userinfobot](https://t.me/userinfobot) |
| `OPENAI_API_KEY` | [OpenRouter](https://openrouter.ai/keys) (`OPENAI_BASE_URL` уже на OpenRouter) |
| `OPENWEATHER_API_KEY` | [OpenWeatherMap](https://home.openweathermap.org/api_keys) |
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |
| `VK_ACCESS_TOKEN` | [VK Apps](https://vk.com/apps) → Standalone → сервисный ключ |
| `NEWS_API_KEY` | [NewsAPI](https://newsapi.org/register) |
| `GOOGLE_CREDENTIALS_FILE` | Service account для Google Sheets |
| `JWT_SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | задаются вручную |

Лог-бот (`TELEGRAM_LOGBOT_TOKEN`) опционален — оставьте пустым, если не нужен.

### 2. Запуск через Make

```bash
make init          # поднимает инфру (Postgres + Redis), затем backend
```

Или по отдельности:

```bash
make infra-up      # PostgreSQL + Redis
make backend-up    # api + bot + scheduler + logbot
make frontend-up   # фронтенд
```

API будет доступен на `http://localhost:8000` (порт из `PORT_API`).


## Качество кода

Используются `ruff` и `ty` — ошибки не игнорируются, исправляются все.

```bash
ty check .
ruff check . --fix
```
