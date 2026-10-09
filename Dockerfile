FROM python:3.12-slim

# uWSGI/gunicorn-friendly, non-root runtime.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# The app writes no local state; caches live in memory (or CACHE_DIR if set).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /srv/app
USER appuser

EXPOSE ${PORT}

COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Exec form so gunicorn is PID 1 and receives SIGTERM for graceful shutdown.
ENTRYPOINT ["docker-entrypoint.sh"]
