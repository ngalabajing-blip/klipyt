FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: ffmpeg for video, libgl + glib for OpenCV/MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        unzip \
        libgl1 \
        libglib2.0-0 \
        libsndfile1 \
        ca-certificates \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install deno (required by yt-dlp for YouTube JS extraction)
RUN curl -fsSL https://deno.land/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

WORKDIR /app

# Install Python deps first for layer caching
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY app ./app
COPY tests ./tests
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

EXPOSE 8000

# Process model: API by default. Override CMD to run the worker.
#   web:    uvicorn app.main:app --host 0.0.0.0 --port 8000
#   worker: python -m app.workers.queue
CMD ["sh", "./start.sh"]
