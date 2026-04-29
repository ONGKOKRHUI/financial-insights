# FinSight — Jarvis Voice Assistant Deployment Guide

This guide covers how to deploy the Jarvis Voice Assistant for the FinSight platform, both locally (Docker) and in production (Vercel/Render).

---

## 🎙 Jarvis Voice Assistant Features

- **Hands-free Navigation**: Navigate company profiles and data by voice.
- **Dual ASR Engines**:
  - **Gemini Audio API**: High-performance cloud transcription (Primary).
  - **Whisper Large V3**: Local, private transcription for Docker/Dev environments.
- **Integrated UI**: Premium floating button with animated rings, status panel, and toast notifications.
- **Keyboard Shortcuts**: Press `J` to start/stop listening.

---

## 🐳 Local Deployment with Docker Compose

Docker Compose is the recommended way to run the entire stack (PostgreSQL + Backend + Frontend) locally.

### 1. Configure Environment
Copy `.env.example` to `.env` in the project root and set the following Jarvis variables:

```bash
# JARVIS_ASR_ENGINE: 'gemini' (cloud) or 'whisper' (local)
JARVIS_ASR_ENGINE=whisper

# Required for Gemini ASR
GOOGLE_API_KEY=your_google_api_key

# Optional: Intent engine (keyword is default and requires no setup)
JARVIS_INTENT_ENGINE=keyword
```

### 2. Start Services
```bash
docker compose up --build
```

- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8000/docs

---

## 💻 Local Development (Local Machine)

If you are not using Docker, follow these steps:

### 1. Backend Setup
```bash
cd src/backend

# Install dependencies
pip install -r requirements.txt

# For local Whisper ASR (Optional)
pip install setuptools
pip install -r requirements-whisper.txt --no-build-isolation
```

### 2. Run Backend with Environment Variables
```bash
# From project root
env $(grep -v '^#' .env | grep -v '^$' | xargs) uvicorn src.backend.main:app --reload
```

---

## 🚢 Production Deployment

### 1. Render (Backend)
- Set up your FastAPI service on Render.
- Add the following environment variables in the Render dashboard:
  - `DATABASE_URL`: Your Supabase URI.
  - `ALLOWED_ORIGINS`: Your Vercel frontend URL.
  - `GOOGLE_API_KEY`: Your Gemini API key.
  - `JARVIS_ASR_ENGINE`: `gemini`.

### 2. Vercel (Frontend)
- Deploy the `frontend/` directory to Vercel.
- Add the following environment variable in the Vercel dashboard:
  - `NEXT_PUBLIC_API_URL`: Your Render backend URL (e.g., `https://finsight-api.onrender.com`).

---

## 🎙 Supported Voice Commands

| Category | Example Phrases |
|----------|-----------------|
| **Companies** | "Show me Maybank", "Go to CIMB", "Petronas", "Sunway" |
| **Global** | "Home", "Main Page", "All Companies", "Browse" |
| **Technical** | "API Docs", "Swagger", "Health" |

---

## 🧪 Testing Jarvis
Verify the Jarvis subsystem is live:
```bash
curl http://localhost:8000/api/jarvis/health
```
Expected response:
```json
{
    "status": "ok",
    "asr_engine": "gemini",
    "intent_engine": "keyword"
}
```
