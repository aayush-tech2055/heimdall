# Heimdall backend: FastAPI + FFmpeg (video review) + Presidio with the small spaCy model.
# Build from the backend/ folder. Set WITH_PRIVACY=false to skip Presidio on tiny instances
# (emails, phone numbers, IDs and confidential terms are still masked by regex).
FROM python:3.12-slim

ARG WITH_PRIVACY=true
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN if [ "$WITH_PRIVACY" = "true" ]; then \
      pip install ".[privacy]" && python -m spacy download en_core_web_sm; \
    else pip install .; fi

RUN useradd --create-home heimdall && mkdir -p .cache && chown -R heimdall /app
USER heimdall

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
