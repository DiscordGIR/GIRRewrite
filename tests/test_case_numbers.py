from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import unittest

import mongoengine

from data.model import Guild
from tests.support import load_module, connect_test_database


class CaseNumberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        connect_test_database()
        module = load_module("data/services/guild_service.py", {
            "utils": SimpleNamespace(cfg=SimpleNamespace(guild_id=123)),
        })
        cls.service = module.GuildService()

    @classmethod
    def tearDownClass(cls):
        mongoengine.disconnect()

    def setUp(self):
        Guild.drop_collection()

    def test_concurrent_allocations_preserve_next_unused_number(self):
        Guild(_id=123, case_id=42).save()
        with ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(lambda _: self.service.allocate_case_id(), range(100)))
        self.assertEqual(sorted(numbers), list(range(42, 142)))
        self.assertEqual(Guild.objects(_id=123).get().case_id, 142)

    def test_missing_guild_does_not_silently_create_a_counter(self):
        with self.assertRaises(RuntimeError):
            self.service.allocate_case_id()
        self.assertEqual(Guild.objects.count(), 0)
