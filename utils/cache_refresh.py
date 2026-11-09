"""Single-flight snapshots with TTL and generation-safe invalidation.

Loaders only live while callers are waiting. Cancelling one waiter never cancels
another waiter's refresh; cancelling the last waiter cleans up the loader.
"""
import asyncio
from time import monotonic


class SnapshotCache:
    def __init__(self, ttl=3600, stale_on_error=False):
        self.closed = False
        self.ttl = ttl
        self.stale_on_error = stale_on_error
        self.values = {}
        self.generations = {}
        self.pending = {}
        self.waiters = {}

    def invalidate(self, key):
        self.generations[key] = self.generations.get(key, 0) + 1
        self.values.pop(key, None)
        self.pending.pop(key, None)

    async def get(self, key, loader):
        while True:
            if self.closed:
                raise RuntimeError("Snapshot cache is closed")
            generation = self.generations.get(key, 0)
            previous = self.values.get(key)
            if previous is not None and previous[0] > monotonic():
                return previous[1]
            task = self.pending.get(key)
            if task is None:
                task = asyncio.create_task(loader())
                self.pending[key] = task
            self.waiters[task] = self.waiters.get(task, 0) + 1
            try:
                try:
                    value = await asyncio.shield(task)
                except Exception:
                    if generation != self.generations.get(key, 0):
                        continue
                    if not self.stale_on_error or previous is None:
                        raise
                    # Keep the last validated value, with a short retry interval.
                    self.values[key] = (monotonic() + min(30, self.ttl), previous[1])
                    return previous[1]
                if generation != self.generations.get(key, 0):
                    continue
                self.values[key] = (monotonic() + self.ttl, value)
                return value
            finally:
                self.waiters[task] -= 1
                if not self.waiters[task]:
                    del self.waiters[task]
                    if self.pending.get(key) is task:
                        del self.pending[key]
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    async def close(self):
        self.closed = True
        tasks = set(self.waiters)
        for key in set(self.values) | set(self.pending):
            self.invalidate(key)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
