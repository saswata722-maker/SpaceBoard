#!/bin/sh
# Container entrypoint.
#
# Platforms inject $PORT (Render, Railway, Cloud Run); docker-compose does not.
# A script is used rather than shell-form CMD so gunicorn runs as PID 1 and
# receives SIGTERM directly for graceful shutdown.
set -e

: "${PORT:=8000}"

exec gunicorn wsgi:app \
    --bind "0.0.0.0:${PORT}" \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
