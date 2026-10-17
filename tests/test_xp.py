from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

import mongoengine
from data.model import User
from tests.support import load_module, connect_test_database


class XpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        connect_test_database()
        cls.module = load_module("data/services/xp_service.py")

    @classmethod
    def tearDownClass(cls):
        mongoengine.disconnect()

    def setUp(self):
        User.drop_collection()

    def test_existing_profile_uses_one_operation_without_level_change(self):
        User(_id=1, xp=100, level=self.module.level_for_xp(100)).save()
        collection = User._get_collection()
        with patch.object(collection, "find_one_and_update", wraps=collection.find_one_and_update) as update:
            with patch.object(collection, "update_one", wraps=collection.update_one) as other:
                result = self.module.award_xp(1, 1)
        self.assertEqual(result.xp, 101)
        self.assertEqual(update.call_count, 1)
        other.assert_not_called()

    def test_frozen_and_clem_profiles_are_not_awarded_xp(self):
        for member_id, flag in [(1, "is_xp_frozen"), (2, "is_clem")]:
            User(_id=member_id, xp=100, **{flag: True}).save()
            self.assertIsNone(self.module.award_xp(member_id, 11))
            self.assertEqual(User.objects(_id=member_id).get().xp, 100)

    def test_concurrent_awards_create_one_profile_without_losing_xp(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.module.award_xp(1, 11), range(100)))
        self.assertEqual(User.objects.count(), 1)
        user = User.objects(_id=1).get()
        self.assertEqual(user.xp, 1100)
        self.assertEqual(user.level, self.module.level_for_xp(1100))

    def test_legacy_level_thresholds(self):
        for xp, expected in [(0, 2), (44, 2), (45, 3), (134, 3), (135, 4)]:
            self.assertEqual(self.module.level_for_xp(xp), expected)
