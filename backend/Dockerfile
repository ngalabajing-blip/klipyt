# Stage 1: pull the prebuilt BgUtils PO-Token provider so we don't have
# to rerun ``npm ci`` + ``tsc`` on every image build. The image already
# contains the bundled Node runtime + transpiled server under /app.
# Pinned to match the ``bgutil-ytdlp-pot-provider`` Python plugin
# version installed below — both must move in lockstep.
FROM brainicism/bgutil-ytdlp-pot-provider:1.3.1 AS bgutil

# Stage 2: actual backend image.
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
RUN curl -fsSL https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip && \
    unzip /tmp/deno.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/deno && \
    rm /tmp/deno.zip && \
    deno --version

# Pull the prebuilt BgUtils server + its bundled node binary into the
# image. The runtime is invoked from start.sh as a sidecar before the
# worker comes up. Keeps the image self-contained without us having to
# transpile TypeScript at build time.
COPY --from=bgutil /usr/local/bin/node /usr/local/bin/node
COPY --from=bgutil /app /opt/bgutil-server

WORKDIR /app

# Install Python deps first for layer caching. The ``bgutil-ytdlp-pot-provider``
# package is the yt-dlp plugin that talks to the sidecar HTTP server.
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install -e . \
    && pip install bgutil-ytdlp-pot-provider==1.3.1

COPY app ./app
COPY tests ./tests
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

EXPOSE 8000

# Process model: API by default. Override CMD to run the worker.
#   web:    uvicorn app.main:app --host 0.0.0.0 --port 8000
#   worker: python -m app.workers.queue
CMD ["sh", "./start.sh"]
