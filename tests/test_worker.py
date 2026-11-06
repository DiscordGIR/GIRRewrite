import asyncio
import threading
import unittest
from tests.support import load_module


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_does_not_release_a_running_worker_slot(self):
        pool = load_module("utils/worker.py").BlockingIOPool(workers=1)
        started = threading.Event()
        release = threading.Event()
        second_started = threading.Event()

        def slow():
            started.set()
            release.wait(timeout=2)

        first = asyncio.create_task(pool.run(slow))
        try:
            await asyncio.to_thread(started.wait, 1)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            second = asyncio.create_task(pool.run(second_started.set))
            await asyncio.sleep(0.02)
            self.assertFalse(second_started.is_set())
            release.set()
            await second
            self.assertTrue(second_started.is_set())
        finally:
            release.set()
            await pool.close()

    async def test_errors_propagate_and_capacity_is_reusable(self):
        pool = load_module("utils/worker.py").BlockingIOPool(workers=1)
        try:
            with self.assertRaises(ZeroDivisionError):
                await pool.run(lambda: 1 / 0)
            self.assertEqual(await pool.run(lambda: 42), 42)
        finally:
            await pool.close()
