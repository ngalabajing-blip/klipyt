#!/bin/sh
set -e

# Start RQ worker in background
python -m app.workers.queue &

# Start API server in foreground
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
