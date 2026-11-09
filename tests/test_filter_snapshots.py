import asyncio
import threading
import os
import subprocess
import sys
import inspect
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import mongoengine
from data.database import configure_database_pool
from data.model import Guild, FilterWord, Tag
from tests.support import connect_test_database, load_module


class SnapshotCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cache = load_module('utils/cache_refresh.py').SnapshotCache()

    async def asyncTearDown(self):
        await self.cache.close()

    async def test_misses_share_loader_and_one_cancelled_waiter_does_not_cancel_it(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def load():
            entered.set()
            await release.wait()
            return ('fresh',)
        loader = AsyncMock(side_effect=load)
        pending = [asyncio.create_task(self.cache.get('key', loader)) for _ in range(20)]
        await entered.wait()
        pending[0].cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending[0]
        release.set()
        self.assertEqual(await asyncio.gather(*pending[1:]), [('fresh',)] * 19)
        loader.assert_awaited_once()

    async def test_invalidation_during_refresh_rejects_old_result(self):
        entered, release = asyncio.Event(), asyncio.Event()
        count = 0
        async def load():
            nonlocal count
            count += 1
            if count == 1:
                entered.set()
                await release.wait()
                return 'old'
            return 'new'
        pending = asyncio.create_task(self.cache.get('key', load))
        await entered.wait()
        self.cache.invalidate('key')
        self.assertEqual(await self.cache.get('key', load), 'new')
        release.set()
        self.assertEqual(await pending, 'new')
        self.assertEqual(count, 2)

    async def test_last_waiter_cancellation_cleans_loader_and_retry_succeeds(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        async def load():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        pending = asyncio.create_task(self.cache.get('key', load))
        await entered.wait()
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertTrue(cancelled.is_set())
        self.assertFalse(self.cache.pending)
        self.assertEqual(await self.cache.get('key', AsyncMock(return_value='retry')), 'retry')

    async def test_error_does_not_poison_cache_and_close_rejects_new_gets(self):
        with self.assertRaises(ValueError):
            await self.cache.get('key', AsyncMock(side_effect=ValueError('failed')))
        self.assertEqual(await self.cache.get('key', AsyncMock(return_value='good')), 'good')
        await self.cache.close()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            await self.cache.get('key', AsyncMock(return_value='late'))


class FilterSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        connect_test_database()
        Guild.drop_collection()
        self.pool = load_module('utils/worker.py').BlockingIOPool(workers=2)
        configure_database_pool(self.pool)
        self.module = load_module('data/services/guild_service.py', {
            'utils': NS(cfg=NS(guild_id=123)),
        })
        self.service = self.module.guild_service
        Guild(_id=123, case_id=1, filter_words=[self.word('bad')],
              tags=[Tag(name='first', content='body'), Tag(name='second', content='other')],
              memes=[Tag(name='meme', content='body'), Tag(name='second', content='other')]).save()

    def word(self, text, **flags):
        return FilterWord(word=text, bypass=5, notify=False, **flags)

    async def asyncTearDown(self):
        await self.service.snapshots.close()
        await self.pool.close()
        configure_database_pool(None)
        mongoengine.disconnect()

    async def test_frozen_snapshots_and_failed_write_preserve_policy(self):
        original = await self.service.get_filtered_words()
        with self.assertRaises(AttributeError):
            original[0].piracy = True
        with patch.object(self.module._repository, 'toggle_filtered_word_flag', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                await self.service.toggle_filtered_word_flag('bad', 'piracy')
        self.assertIs(await self.service.get_filtered_words(), original)
        self.assertFalse(Guild.objects.get().filter_words[0].piracy)
        self.assertTrue(await self.service.toggle_filtered_word_flag('bad', 'piracy'))
        self.assertTrue((await self.service.get_filtered_words())[0].piracy)
        self.assertFalse(original[0].piracy)

    async def test_independent_flag_updates_preserve_other_fields(self):
        await asyncio.gather(self.service.toggle_filtered_word_flag('bad', 'piracy'),
                             self.service.toggle_filtered_word_flag('bad', 'silent_filter'))
        word = (await self.service.get_filtered_words())[0]
        self.assertTrue(word.piracy)
        self.assertTrue(word.silent_filter)
        self.assertEqual((word.word, word.bypass, word.notify), ('bad', 5, False))

    async def test_legacy_missing_flag_and_bounded_contention(self):
        Guild._get_collection().update_one({'_id': 123}, {'$unset': {'filter_words.0.piracy': ''}})
        self.assertTrue(await self.service.toggle_filtered_word_flag('bad', 'piracy'))
        from mongoengine.queryset import QuerySet
        with patch.object(QuerySet, 'update_one', return_value=0) as update:
            with self.assertRaisesRegex(RuntimeError, 'please retry'):
                await self.service.toggle_filtered_word_flag('bad', 'piracy')
            self.assertEqual(update.call_count, 8)

    async def test_projections_and_atomic_counters(self):
        collection = Guild._get_collection()
        with patch.object(collection, 'find_one_and_update', wraps=collection.find_one_and_update) as modify:
            self.assertEqual(await self.service.allocate_case_id(), 1)
            self.assertEqual(modify.call_args.kwargs['projection'], {'case_id': 1, '_id': 1})
            tag = await self.service.get_tag('first')
            self.assertEqual((tag.name, tag.use_count), ('first', 1))
            self.assertEqual(modify.call_args.kwargs['projection'], {'tags': {'$elemMatch': {'name': 'first'}}, '_id': 1})
            meme = await self.service.get_meme('meme')
            self.assertEqual(meme.use_count, 1)
            self.assertEqual(modify.call_args.kwargs['projection'], {'memes': {'$elemMatch': {'name': 'meme'}}, '_id': 1})
        with patch.object(collection, 'find', wraps=collection.find) as find:
            self.assertEqual(await self.service.get_content_names('tags'), ('first', 'second'))
            self.assertEqual(find.call_args.kwargs['projection'], {'tags.name': 1, '_id': 1})
            self.assertFalse(await self.service.get_config_value('sabbath_mode'))
            self.assertEqual(find.call_args.kwargs['projection'], {'sabbath_mode': 1, '_id': 1})
        self.assertEqual(Guild.objects.get().tags[1].use_count, 0)
        self.assertEqual(Guild.objects.get().case_id, 2)

    @unittest.skipUnless(os.environ.get('GIR_TEST_MONGO_URI'), 'Non-first positional updates require real MongoDB; mongomock updates the first element')
    async def test_nonfirst_tag_projection_preserves_atomic_increment(self):
        for field, getter in [('tags', self.service.get_tag), ('memes', self.service.get_meme)]:
            with self.subTest(field=field):
                item = await getter('second')
                self.assertEqual((item.name, item.use_count), ('second', 1))
                self.assertEqual(getattr(Guild.objects.get(), field)[0].use_count, 0)

    async def test_cancelled_write_still_invalidates_after_completion(self):
        original = await self.service.get_filtered_words()
        entered, release = threading.Event(), threading.Event()
        toggle = self.module._repository.toggle_filtered_word_flag
        def slow_toggle(*args):
            entered.set()
            if not release.wait(3):
                raise AssertionError('write barrier timed out')
            return toggle(*args)
        with patch.object(self.module._repository, 'toggle_filtered_word_flag', side_effect=slow_toggle):
            pending = asyncio.create_task(self.service.toggle_filtered_word_flag('bad', 'piracy'))
            try:
                while not entered.is_set():
                    await asyncio.sleep(0.001)
                pending.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await pending
            finally:
                release.set()
            async def invalidated():
                while not self.service.snapshots.generations.get('filter_words'):
                    await asyncio.sleep(0.001)
            await asyncio.wait_for(invalidated(), 2)
        self.assertTrue((await self.service.get_filtered_words())[0].piracy)
        self.assertFalse(original[0].piracy)

    async def test_filter_semantics_unicode_flags_bypass_and_order(self):
        gatekeeper = NS(has=Mock(return_value=False))
        module = load_module('utils/framework/filter.py', {
            'data.services': NS(guild_service=self.service),
            'utils.framework': NS(gatekeeper=gatekeeper),
        })
        member = NS(guild=object())
        cases = [('BAD', True), ('b.a.d', True), ('b a d', True), ('bаd', True),
                 ('::bad::', True), ('nothing', False)]
        for text, matched in cases:
            with self.subTest(text=text):
                self.assertEqual(bool(await module.find_triggered_filters(text, member)), matched)
        await self.service.toggle_filtered_word_flag('bad', 'false_positive')
        self.assertFalse(await module.find_triggered_filters('badly', member))
        self.assertFalse(await module.find_triggered_filters('b.a.d', member))
        self.assertTrue(await module.find_triggered_filters('a bad word', member))
        await self.service.add_filtered_word(self.word('word', silent_filter=True, piracy=True))
        hits = await module.find_triggered_filters('bad word', member)
        self.assertEqual([hit.word for hit in hits], ['bad', 'word'])
        self.assertTrue(hits[1].silent_filter and hits[1].piracy)
        await self.service.add_filtered_word(FilterWord(word='notice', bypass=5, notify=True))
        self.assertEqual([hit.word for hit in await module.find_triggered_filters('bad notice word', member)], ['notice'])
        gatekeeper.has.return_value = True
        self.assertFalse(await module.find_triggered_filters('bad notice word', member))

    async def test_word_and_raid_compact_semantics_remain_distinct(self):
        gatekeeper = NS(has=Mock(return_value=False))
        module = load_module('utils/framework/filter.py', {
            'data.services': NS(guild_service=self.service),
            'utils.framework': NS(gatekeeper=gatekeeper),
        })
        await self.service.add_filtered_word(self.word('two words'))
        await self.service.add_raid_phrase('two words')
        member = NS(guild=object())
        self.assertTrue(await module.find_triggered_filters('twowords', member))
        self.assertIsNone(await module.find_triggered_raid_phrases('twowords', member))
        self.assertEqual((await module.find_triggered_raid_phrases('two words', member)).word, 'two words')


class CommandSnapshotTests(unittest.TestCase):
    def test_real_filter_commands_update_without_mutating_snapshots(self):
        from tests.support import ROOT
        result = subprocess.run([sys.executable, '-c',
            'import asyncio, os, sys; sys.path.insert(0, os.getcwd()); from tests.boot_smoke import check; '
            'from tests.test_filter_snapshots import command_assertions; '
            'asyncio.run(check(command_assertions))'], cwd=ROOT,
            capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


async def command_assertions(bot):
    from cogs.commands.mod.filter import Filters
    from data.services import guild_service
    await guild_service.add_filtered_word(FilterWord(word='Mixed', bypass=5, notify=False))
    original = await guild_service.get_filtered_words()
    ctx = NS(send_success=AsyncMock(), send_warning=AsyncMock())
    cog = bot.get_cog('Filters')
    for flag in ('silent_filter', 'piracy', 'falsepositive'):
        await inspect.unwrap(getattr(Filters, flag).callback)(cog, ctx, word='MIXED')
    current = (await guild_service.get_filtered_words())[0]
    assert current.silent_filter and current.piracy and current.false_positive
    assert not original[0].silent_filter and not original[0].piracy
    assert ctx.send_success.await_count == 3
    ctx.send_warning.assert_not_awaited()
