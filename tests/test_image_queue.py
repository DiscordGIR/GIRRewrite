import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from tests.support import load_module


class ImageQueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        worker = load_module("utils/worker.py")
        self.module = load_module("cogs/monitors/mod/antiraid.py", {
            "data.services": Mock(),
            "utils": SimpleNamespace(cfg=SimpleNamespace(roles=SimpleNamespace(member_plus=1)),
                                     fetchers=Mock(), logger=Mock()),
            "utils.worker": worker,
            "utils.antiraid": SimpleNamespace(download_image=Mock(), image_fingerprint=Mock(),
                                              is_image=lambda attachment: True, match_fingerprint=Mock()),
            "utils.framework": Mock(),
            "utils.mod": Mock(),
            "utils.views": Mock(),
            "utils.views.menus.antiraid": Mock(),
        })
        self.monitor = self.module.AntiRaidMonitor.__new__(self.module.AntiRaidMonitor)
        self.monitor.image_queue = asyncio.Queue(maxsize=2)
        self.monitor.image_scans_dropped = 0

    def message(self):
        return SimpleNamespace(id=123, attachments=[object()], author=SimpleNamespace(
            guild_permissions=SimpleNamespace(administrator=False), roles=[]))

    async def test_overload_is_bounded_and_does_not_punish_members(self):
        self.monitor.apply_content_moderation = AsyncMock()
        for _ in range(100):
            self.monitor.enqueue_images(self.message())
        self.assertEqual(self.monitor.image_queue.qsize(), 2)
        self.assertEqual(self.monitor.image_scans_dropped, 98)
        self.monitor.apply_content_moderation.assert_not_called()

    async def test_worker_continues_after_failed_scan(self):
        self.monitor.image_spam = AsyncMock(side_effect=[ValueError("bad image"), False])
        self.monitor.enqueue_images(self.message())
        self.monitor.enqueue_images(self.message())
        task = asyncio.create_task(self.monitor.scan_images())
        try:
            await asyncio.wait_for(self.monitor.image_queue.join(), timeout=1)
            self.assertEqual(self.monitor.image_spam.await_count, 2)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_inspection_timeout_does_not_apply_punishment(self):
        self.monitor.inspect_images = AsyncMock(side_effect=asyncio.TimeoutError)
        self.monitor.apply_content_moderation = AsyncMock()
        with self.assertRaises(asyncio.TimeoutError):
            await self.monitor.image_spam(self.message())
        self.monitor.apply_content_moderation.assert_not_called()

    async def test_valid_finding_reaches_moderation_and_reporting(self):
        finding = dict(reason="scam", title="test", trigger="match", evidence=[])
        self.monitor.inspect_images = AsyncMock(return_value=finding)
        self.monitor.apply_content_moderation = AsyncMock(return_value=("deleted", None))
        self.monitor.send_content_report = AsyncMock()
        message = self.message()
        self.assertTrue(await self.monitor.image_spam(message))
        self.monitor.send_content_report.assert_awaited_once_with(
            message, **finding, actions="deleted", timeout_until=None)
