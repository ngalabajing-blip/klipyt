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

# Start the BgUtils PO-Token provider as a local sidecar. yt-dlp's
# bgutil-ytdlp-pot-provider plugin points at http://127.0.0.1:4416 by
# default and uses POT to authenticate web/mweb player_client requests
# without us having to maintain a logged-in cookie file. The server
# image was copy-mounted from the multi-stage Dockerfile build at
# /opt/bgutil-server.
BGUTIL_PORT="${BGUTIL_PORT:-4416}"
if [ -f /opt/bgutil-server/build/main.js ]; then
    echo "[bgutil] starting POT provider on port ${BGUTIL_PORT}"
    (
        cd /opt/bgutil-server
        node build/main.js --port "${BGUTIL_PORT}"
    ) &
    BGUTIL_PID=$!
    # Best-effort readiness check: poll /ping for up to ~10s.
    i=0
    while [ $i -lt 20 ]; do
        if curl -fsS "http://127.0.0.1:${BGUTIL_PORT}/ping" >/dev/null 2>&1; then
            echo "[bgutil] ready (pid=${BGUTIL_PID})"
            break
        fi
        i=$((i + 1))
        sleep 0.5
    done
else
    echo "[bgutil] /opt/bgutil-server/build/main.js missing — POT disabled"
fi

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
