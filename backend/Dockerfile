# Populated when container build is finalized for deployment.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
# Non-root user — avoids Celery SecurityWarning and matches production practice.
RUN groupadd --gid 1000 appuser \
  && useradd --uid 1000 --gid appuser --shell /sbin/nologin --create-home appuser \
  && chown -R appuser:appuser /app
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
