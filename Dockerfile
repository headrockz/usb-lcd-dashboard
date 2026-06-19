FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONWARNINGS=ignore

RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
       openssh-client \
    && apt-get clean autoclean \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip poetry

COPY . /app/usb-lcd-dashboard

WORKDIR /app/usb-lcd-dashboard

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

CMD ["python", "homelab_monitor.py"]
