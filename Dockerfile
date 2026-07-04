FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JM_SERVICE_DATA_DIR=/data \
    JM_DOWNLOAD_DIR=/data/downloads \
    JM_OPTION_PATH=/app/docker/option.yml

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip

COPY pyproject.toml setup.py README.md LICENSE ./
COPY src ./src
COPY requirements-service.txt ./requirements-service.txt

RUN python -m pip install --no-cache-dir . \
    && python -m pip install --no-cache-dir -r requirements-service.txt

COPY service ./service
COPY docker ./docker

RUN mkdir -p /data/tasks /data/archives /data/downloads

EXPOSE 8000

CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
