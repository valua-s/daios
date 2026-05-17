#!/bin/sh
set -e

mkdir -p /app/logs

exec "$@"
