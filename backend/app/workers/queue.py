"""RQ queue and worker entrypoint."""

from __future__ import annotations

from functools import lru_cache

import redis
from rq import Queue, Worker

from app.config import settings


@lru_cache
def redis_conn() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url)


@lru_cache
def default_queue() -> Queue:
    return Queue("default", connection=redis_conn(), default_timeout=60 * 60)


def main() -> None:  # pragma: no cover - process entrypoint
    worker = Worker([default_queue()], connection=redis_conn())
    worker.work()


if __name__ == "__main__":  # pragma: no cover
    main()
