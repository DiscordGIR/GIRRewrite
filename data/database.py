"""Awaitable boundary for MongoEngine and GridFS work.

Configured once by Bot.setup_hook. Repository methods must finish all queries
before returning; documents belong to the caller and must not be shared between
concurrent operations. Never pass Discord API operations to this worker pool.
"""
from functools import wraps

_pool = None


def configure_database_pool(pool):
    global _pool
    _pool = pool


async def run_database(function, *args, **kwargs):
    if _pool is None:
        raise RuntimeError("Database worker pool has not been configured")
    return await _pool.run(function, *args, **kwargs)


def database_method(function):
    """Expose a synchronous repository operation as an awaitable service method."""
    @wraps(function)
    async def invoke(self, *args, **kwargs):
        return await run_database(function, *args, **kwargs)
    return invoke
