FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONWARNINGS=ignore

# Install Docker CLI from official repository
RUN apt-get update && apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       openssh-client \
       docker-ce-cli \
    && apt-get clean autoclean \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip poetry

COPY . /app/usb-lcd-dashboard

WORKDIR /app/usb-lcd-dashboard

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

CMD ["python", "homelab_monitor.py"]
