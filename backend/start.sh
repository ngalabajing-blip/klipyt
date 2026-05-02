#!/bin/sh
set -e

# Install deno if not available (required by yt-dlp for the YouTube
# n-challenge JS solver).
if ! command -v deno >/dev/null 2>&1; then
    echo "Installing deno..."
    curl -fsSL https://deno.land/install.sh | sh
    export DENO_INSTALL="/root/.deno"
    export PATH="$DENO_INSTALL/bin:$PATH"
fi

echo "Deno: $(deno --version | head -1)"
echo "yt-dlp: $(yt-dlp --version)"

# Run the RQ worker under a tiny supervisor loop so that an OOM or
# yt-dlp crash on a stuck job doesn't take the worker offline forever.
# Without this, a single bad video can leave the queue stuck on
# "downloading 5%" indefinitely (no worker to dequeue new jobs).
worker_supervisor() {
    while true; do
        echo "[supervisor] starting RQ worker"
        python -m app.workers.queue || echo "[supervisor] worker exited rc=$?"
        echo "[supervisor] worker died — restarting in 3s"
        sleep 3
    done
}

worker_supervisor &

# Start API server in foreground.
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
