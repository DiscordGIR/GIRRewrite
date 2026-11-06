import unittest
from unittest.mock import patch
from tests.support import load_module


class LogQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_logging_backlog_is_bounded(self):
        with patch("sys.argv", ["test", "--disable-discord-logs", "--disable-scheduler-logs",
                                "--disable-webhook-logging"]), patch("dotenv.main.load_dotenv"):
            module = load_module("utils/logging.py")
        module.start_webhook_logging()
        try:
            for _ in range(1000):
                module.enqueue_webhook("https://example.invalid", {"content": "message"})
            self.assertEqual(module._webhook_queue.qsize(), 200)
            self.assertEqual(module.webhook_logs_dropped, 800)
        finally:
            await module.stop_webhook_logging()
        self.assertIsNone(module._webhook_task)
        self.assertIsNone(module._webhook_queue)
