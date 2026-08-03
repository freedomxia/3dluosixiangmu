FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RUNTIME_DIR=/app/.runtime

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY SKILL.md .
COPY references ./references
COPY scripts ./scripts
COPY webapp ./webapp

RUN mkdir -p /app/config /app/generated /app/.runtime \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app/generated /app/.runtime

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"

CMD ["uvicorn", "webapp.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
