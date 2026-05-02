#!/bin/sh
set -e

# Install deno if not available
if ! command -v deno >/dev/null 2>&1; then
    echo "Installing deno..."
    curl -fsSL https://deno.land/install.sh | sh
    export DENO_INSTALL="/root/.deno"
    export PATH="$DENO_INSTALL/bin:$PATH"
fi

echo "Deno: $(deno --version | head -1)"

# Start RQ worker in background
python -m app.workers.queue &

# Start API server in foreground
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
