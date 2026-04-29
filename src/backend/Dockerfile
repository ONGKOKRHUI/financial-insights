FROM python:3.12-slim

# Install ffmpeg for Whisper audio processing
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install base requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install faster-whisper (CTranslate2 backend — Python 3.12 compatible)
COPY requirements-whisper.txt .
RUN pip install --no-cache-dir -r requirements-whisper.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
