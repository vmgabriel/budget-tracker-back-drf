# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app --shell /usr/sbin/nologin app \
    && mkdir -p /app/staticfiles /opt \
    && chown -R app:app /app /opt

FROM base AS builder
USER app

COPY --chown=app:app pyproject.toml README.md ./
COPY --chown=app:app src ./src

RUN python -m venv /opt/venv \
    && pip install --upgrade pip \
    && pip install .

FROM builder AS test
USER app
RUN pip install ".[test]"

FROM base AS runtime

USER root
RUN apt-get update \
    && apt-get install --no-install-recommends --yes curl \
    && rm -rf /var/lib/apt/lists/*

USER app
COPY --from=builder --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app manage.py pyproject.toml README.md ./
COPY --chown=app:app src ./src

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/readyz || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
