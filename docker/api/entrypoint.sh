#!/bin/sh
set -e
echo $PYTHONPATH

echo "⏳ Waiting for PostgreSQL..."
wait-for-it "${DB_HOST}:${DB_PORT:-5432}" --timeout=30 --strict -- echo "✅ PostgreSQL is up"

echo "⏳ Waiting for Redis..."
wait-for-it "${REDIS_HOST}:${REDIS_PORT:-6379}" --timeout=30 --strict -- echo "✅ Redis is up"

exec "$@"
