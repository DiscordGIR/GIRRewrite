import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import unittest
from unittest.mock import patch

import mongoengine
from data.model import Guild, User, Cases
from tests.support import load_module, connect_test_database


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        connect_test_database()
        for model in (Guild, User, Cases):
            model.drop_collection()

    def tearDown(self):
        mongoengine.disconnect()

    def test_repeated_setup_preserves_case_counter_and_configuration(self):
        Guild(_id=123, case_id=500, filter_excluded_guilds=[999]).save()
        with patch("dotenv.load_dotenv"), patch.dict(os.environ, {"MAIN_GUILD_ID": "123"}):
            module = load_module("setup.py")
            asyncio.run(module.setup())
        guild = Guild.objects(_id=123).get()
        self.assertEqual(guild.case_id, 500)
        self.assertEqual(guild.filter_excluded_guilds, [999])

    def test_concurrent_profile_and_case_creation_is_safe(self):
        service = load_module("data/services/user_service.py").UserService()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: (service.get_user(123), service.get_cases(123)), range(100)))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Cases.objects.count(), 1)
