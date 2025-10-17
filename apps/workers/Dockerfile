
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY apps/workers/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/workers /app
ENV PYTHONUNBUFFERED=1
CMD ["bash", "-lc", "echo 'Specify Celery command in compose.yml' && sleep infinity"]
