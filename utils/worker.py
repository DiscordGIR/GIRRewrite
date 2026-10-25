"""Bound synchronous integrations without sharing Discord objects with workers."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from time import monotonic


class BlockingIOPool:
    def __init__(self, workers=4, name="gir-io"):
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=name)
        self.slots = asyncio.Semaphore(workers)
        self.closed = False
        self.completed = 0
        self.total_seconds = 0.0

    async def run(self, function, *args, **kwargs):
        if self.closed:
            raise RuntimeError("Worker pool is closed")
        await self.slots.acquire()
        if self.closed:
            self.slots.release()
            raise RuntimeError("Worker pool is closed")
        started = monotonic()
        try:
            future = asyncio.get_running_loop().run_in_executor(
                self.executor, partial(function, *args, **kwargs))
        except BaseException:
            self.slots.release()
            raise

        def finished(result):
            self.completed += 1
            self.total_seconds += monotonic() - started
            self.slots.release()
            # Retrieve exceptions even when the awaiting caller was cancelled.
            if not result.cancelled():
                result.exception()

        future.add_done_callback(finished)
        # Cancellation must not free capacity while the thread is still running.
        return await asyncio.shield(future)

    async def close(self):
        self.closed = True
        await asyncio.to_thread(self.executor.shutdown, wait=True)
