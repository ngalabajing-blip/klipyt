"""Pytest fixtures."""

from __future__ import annotations

import os

# Force a sqlite test DB and disable real services before any app import.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("MIMO_API_KEY", "test-key")
