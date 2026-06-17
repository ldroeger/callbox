FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y mpg123 alsa-utils && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pyserial requests

COPY . .

CMD ["python", "call_engine.py"]
