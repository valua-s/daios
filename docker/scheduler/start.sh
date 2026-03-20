#!/bin/sh
set -e

echo "⏰ Starting Scheduler..."
exec python -m backend.scheduler
