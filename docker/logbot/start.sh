#!/bin/sh
set -e

echo "📜 Starting Log Bot..."
exec python -m backend.logbot
