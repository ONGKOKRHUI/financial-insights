FROM python:3.12-slim

# Install ffmpeg for Whisper audio processing
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Mirror repo layout under `src/` so `routers/pipeline_trigger.py` can resolve
# `parents[2]` to the real `src/` directory (see sys.path bootstrap there).
WORKDIR /app/src/backend

COPY src/backend/requirements.txt .
COPY src/backend/requirements-whisper.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-whisper.txt

COPY src/backend/ .
COPY src/jobs/ /app/src/jobs/
COPY src/pipeline/ /app/src/pipeline/
COPY src/db/ /app/src/db/

ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
