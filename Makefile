# ── Окружение ───────────────────────────────────────────────────────────
ENV ?= .env

INFRA    = docker compose -f infra.docker-compose.yml    --env-file $(ENV)
BACKEND  = docker compose -f backend.docker-compose.yml  --env-file $(ENV)
FRONTEND = docker compose -f frontend.docker-compose.yml --env-file $(ENV)

.PHONY: \
  infra-up infra-down \
  backend-up backend-down \
  frontend-up frontend-down \
  restart-api restart-bot restart-scheduler restart-frontend \
  up down logs \
  logs-api logs-bot logs-scheduler \
  shell-api shell-bot \
  migrate makemigrations rollback \
  lint lint-fix typecheck test init

# ── Инфра ───────────────────────────────────────────────────────────────

infra-up:
	$(INFRA) up -d

infra-down:
	$(INFRA) down

# ── Бэкенд ──────────────────────────────────────────────────────────────

backend-up:
	$(BACKEND) up -d

back-rebuild:
	$(BACKEND) up --build -d

backend-down:
	$(BACKEND) down

# ── Фронтенд ────────────────────────────────────────────────────────────

frontend-up:
	$(FRONTEND) up -d

frontend-down:
	$(FRONTEND) down

# ── Перезапуск отдельных сервисов ───────────────────────────────────────

restart-api:
	$(BACKEND) up -d --build api

restart-bot:
	$(BACKEND) up -d --build bot

restart-scheduler:
	$(BACKEND) up -d --build scheduler

restart-front:
	$(FRONTEND) up -d --build frontend

# ── Все сразу ───────────────────────────────────────────────────────────

up: infra-up backend-up

down: backend-down infra-down

# ── Логи ────────────────────────────────────────────────────────────────

logs:
	$(BACKEND) logs -f

logs-api:
	$(BACKEND) logs -f api

logs-bot:
	$(BACKEND) logs -f bot

logs-scheduler:
	$(BACKEND) logs -f scheduler

# ── Shell ───────────────────────────────────────────────────────────────

shell-api:
	$(BACKEND) exec api sh

shell-bot:
	$(BACKEND) exec bot sh

# ── Миграции ────────────────────────────────────────────────────────────

makemigrations:
	$(BACKEND) exec api alembic revision --autogenerate -m "$(name)"

migrate:
	$(BACKEND) exec api alembic upgrade head

rollback:
	$(BACKEND) exec api alembic downgrade -1

# ── Качество кода ───────────────────────────────────────────────────────

lint:
	$(BACKEND) exec api ruff check .

lint-fix:
	$(BACKEND) exec api ruff check . --fix

typecheck:
	$(BACKEND) exec api mypy .

test:
	$(BACKEND) exec api pytest -v

# ── Первый запуск ───────────────────────────────────────────────────────

init:
	@echo "🚀 Starting infra..."
	$(MAKE) infra-up ENV=$(ENV)
	@echo "⏳ Waiting for infra to be ready..."
	sleep 6
	@echo "🚀 Starting backend..."
	$(MAKE) backend-up ENV=$(ENV)
	@echo ""
	@echo "✅  DAIOS is running!"
	@echo "🌐  API:    http://localhost:$$(grep ^PORT_API $(ENV) | cut -d= -f2)"
	@echo "📦  Minio:  http://localhost:$$(grep ^PORT_MINIO_CONSOLE $(ENV) | cut -d= -f2)"
