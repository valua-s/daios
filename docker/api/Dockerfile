FROM python:3.14-slim

WORKDIR /app

# Системные зависимости + wait-for-it
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl wget \
    && wget -q https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh \
       -O /usr/local/bin/wait-for-it \
    && chmod +x /usr/local/bin/wait-for-it \
    && rm -rf /var/lib/apt/lists/*

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Зависимости — отдельным слоем для кэша
COPY pyproject.toml .
RUN uv pip install --system --no-cache -e ".[dev]"

COPY . .

COPY docker/api/entrypoint.sh /entrypoint.sh
COPY docker/api/start.sh /start.sh
RUN chmod +x /entrypoint.sh /start.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start.sh"]
