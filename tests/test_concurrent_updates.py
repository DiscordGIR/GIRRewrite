import asyncio
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mongoengine
from mongoengine.queryset import QuerySet

from data.database import configure_database_pool
from data.model import Case, Cases, Guild, Tag, User
from tests.support import connect_test_database, load_module


class ConcurrentUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        connect_test_database()
        for model in (User, Cases, Guild):
            model.drop_collection()
        self.pool = load_module('utils/worker.py').BlockingIOPool(workers=2)
        configure_database_pool(self.pool)
        self.users = load_module('data/services/user_service.py')
        self.guilds = load_module('data/services/guild_service.py', {
            'utils': SimpleNamespace(cfg=SimpleNamespace(guild_id=123)),
        })

    async def asyncTearDown(self):
        await self.pool.close()
        configure_database_pool(None)
        mongoengine.disconnect()

    async def wait_for_thread(self, event):
        async def wait():
            while not event.is_set():
                await asyncio.sleep(0.001)
        await asyncio.wait_for(wait(), 2)

    def warning(self, case_id=1):
        return Case(_id=case_id, _type='WARN', mod_id=2, mod_tag='mod',
                    reason='original', punishment='100')

    async def test_overlapping_lifts_deduct_once(self):
        User(_id=101, warn_points=100).save()
        Cases(_id=101, cases=[self.warning()]).save()
        read = threading.Event()
        release = threading.Event()
        second_started = threading.Event()
        original = self.users._repository.get_cases

        def pause_first_read(member_id):
            result = original(member_id)
            if not read.is_set():
                read.set()
                if not release.wait(3):
                    raise AssertionError('read barrier timed out')
            return result

        def second_lift():
            second_started.set()
            return self.users._repository.lift_warn(101, '1', 'second', 3, 'other')

        with patch.object(self.users._repository, 'get_cases', side_effect=pause_first_read):
            first = asyncio.create_task(self.users.user_service.lift_warn(101, '1', 'first', 2, 'mod'))
            try:
                await self.wait_for_thread(read)
                second = asyncio.create_task(self.pool.run(second_lift))
                await self.wait_for_thread(second_started)
            finally:
                release.set()
            results = await asyncio.gather(first, second, return_exceptions=True)
        self.assertIsInstance(results[0], Case)
        self.assertIsInstance(results[1], ValueError)
        self.assertIn('already lifted', str(results[1]))
        self.assertEqual(User.objects.get(_id=101).warn_points, 0)
        stored = Cases.objects.get(_id=101).cases[0]
        self.assertTrue(stored.lifted)
        self.assertEqual(stored.lifted_reason, 'first')
        self.assertEqual(stored.reason, 'original')
        self.assertEqual(stored.date, results[0].date)

    async def test_rejected_lift_does_not_change_case_or_points(self):
        User(_id=101, warn_points=50).save()
        Cases(_id=101, cases=[self.warning()]).save()
        with self.assertRaisesRegex(ValueError, 'negative'):
            await self.users.user_service.lift_warn(101, '1', 'lift', 2, 'mod')
        self.assertFalse(Cases.objects.get(_id=101).cases[0].lifted)
        self.assertEqual(User.objects.get(_id=101).warn_points, 50)

    async def test_tag_and_meme_reads_cannot_revert_concurrent_edits(self):
        for field, noun in [('tags', 'tag'), ('memes', 'meme')]:
            with self.subTest(field=field):
                Guild.drop_collection()
                Guild(_id=123, case_id=1, **{field: [Tag(name='test', content='old')]}).save()
                read = threading.Event()
                release = threading.Event()
                original = QuerySet.modify

                def pause_after_read(query, *args, **kwargs):
                    result = original(query, *args, **kwargs)
                    read.set()
                    if not release.wait(3):
                        raise AssertionError('read barrier timed out')
                    return result

                getter = getattr(self.guilds.guild_service, 'get_' + noun)
                editor = getattr(self.guilds.guild_service, 'edit_' + noun)
                with patch.object(QuerySet, 'modify', pause_after_read):
                    pending = asyncio.create_task(getter('test'))
                    try:
                        await self.wait_for_thread(read)
                        await editor(Tag(name='test', content='new', button_links=['link']))
                    finally:
                        release.set()
                    await pending
                stored = getattr(Guild.objects.get(_id=123), field)[0]
                self.assertEqual(stored.content, 'new')
                self.assertEqual(stored.button_links, ['link'])
                self.assertEqual(stored.use_count, 1)
                self.assertEqual((await getter('test')).use_count, 2)
                self.assertIsNone(await getter('missing'))
