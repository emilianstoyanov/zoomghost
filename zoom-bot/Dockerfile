FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

# 🛠️ Packages required by cryptography
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    net-tools \
    iputils-ping \
    iproute2 \
    dnsutils \
    vim \
    nano \
    less \
    libmagic1 \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ app/

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--log-level", "debug"]
