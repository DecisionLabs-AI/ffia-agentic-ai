# =============================================================================
# FFIA — Backend Dockerfile (FastAPI + LangGraph agent)
# Reusable across Render (free), Railway, and Google Cloud Run.
# The container binds to $PORT (Render/Cloud Run inject it); defaults to 8000 locally.
# =============================================================================

# Step 1: Slim Python base — matches the app's supported runtime
FROM python:3.12-slim

# Step 2: Runtime env — unbuffered logs, no pip cache (smaller image)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Step 3: Install Python deps first (layer cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 4: Copy the application source (frontend/venv excluded via .dockerignore)
COPY . .

# Step 5: Document the port; the host platform overrides it via $PORT at runtime
EXPOSE 8000

# Step 6: Start Uvicorn — shell form so ${PORT} expands (Render/Cloud Run set it)
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
