# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \ 
    && apt-get install -y --no-install-recommends gcc librdkafka-dev \ 
    && rm -rf /var/lib/apt/lists/*

COPY services/requirements-pipeline.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app
COPY services/rss_ingest/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
