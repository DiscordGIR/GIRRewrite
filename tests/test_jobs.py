import asyncio
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.date import DateTrigger
from tests.support import load_module


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users = AsyncMock()
        self.guilds = AsyncMock()
        self.module = load_module("utils/jobs.py", {
            "utils": SimpleNamespace(cfg=SimpleNamespace(guild_id=123)),
            "data.services": SimpleNamespace(user_service=self.users, guild_service=self.guilds),
        })
        self.bot = SimpleNamespace(loop=asyncio.get_running_loop())
        self.tasks = self.module.Tasks(self.bot)
        self.bot.tasks = self.tasks
        self.store = MemoryJobStore()
        with patch.object(self.module, "MongoDBJobStore", return_value=self.store), patch.dict(
                "os.environ", {"DB_HOST": "localhost", "DB_PORT": "27017"}):
            await self.tasks.start()
        self.scheduler = self.tasks.tasks
        self.deadline = datetime.now(timezone.utc) + timedelta(hours=1)

    async def asyncTearDown(self):
        await self.tasks.close()

    async def test_repeated_timeout_replaces_deadline(self):
        await self.tasks.schedule_untimeout(1, self.deadline)
        later = self.deadline + timedelta(hours=1)
        await self.tasks.schedule_untimeout(1, later)
        self.assertEqual(len(self.scheduler.get_jobs()), 1)
        self.assertEqual(self.scheduler.get_job("timeout:1").next_run_time, later)
        await self.tasks.cancel_unmute(1)
        await self.tasks.cancel_unmute(1)
        self.assertEqual(self.scheduler.get_jobs(), [])

    async def test_distinct_features_and_many_reminders_do_not_collide(self):
        await self.tasks.schedule_untimeout(2, self.deadline)
        await self.tasks.schedule_remove_bday(1, self.deadline)
        for _ in range(200):
            await self.tasks.schedule_reminder(1, "test", self.deadline)
        self.assertEqual(len(self.scheduler.get_jobs()), 202)

    async def test_new_member_deadline_is_not_extended_by_messages(self):
        await self.tasks.schedule_remove_new_member_role(1, self.deadline)
        await self.tasks.schedule_remove_new_member_role(1, self.deadline + timedelta(hours=1))
        self.assertEqual(len(self.scheduler.get_jobs()), 1)
        self.assertEqual(self.scheduler.get_job("new-member:1").next_run_time, self.deadline)

    async def test_replacing_timeout_removes_matching_legacy_job(self):
        await self.tasks._call(self.scheduler.add_job, self.module.untimeout_callback, 'date', id="1",
                               run_date=self.deadline, args=[1])
        await self.tasks.schedule_untimeout(1, self.deadline)
        self.assertIsNone(self.scheduler.get_job("1"))
        self.assertIsNotNone(self.scheduler.get_job("timeout:1"))

    async def test_cancel_does_not_remove_other_feature_with_numeric_id(self):
        await self.tasks._call(self.scheduler.add_job, self.module.remove_bday_callback, 'date', id="2",
                               run_date=self.deadline, args=[1])
        await self.tasks.cancel_unmute(2)
        self.assertIsNotNone(self.scheduler.get_job("2"))

    async def test_old_timeout_job_never_clears_current_punishment(self):
        member = Mock()
        member.is_timed_out.return_value = True
        self.module.BOT_GLOBAL = Mock()
        self.module.BOT_GLOBAL.get_guild.return_value.get_member.return_value = member
        await self.module.remove_timeout(1)
        member.edit.assert_not_called()
        self.users.add_case.assert_not_called()

    async def test_callback_awaits_real_work_and_propagates_failure(self):
        self.module.BOT_GLOBAL = self.bot
        self.module.remind = AsyncMock(side_effect=RuntimeError("delivery failed"))
        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            await self.module.reminder_callback(1, "hello")
        self.module.remind.assert_awaited_once_with(1, "hello")

    async def test_slow_job_store_does_not_block_bot_loop(self):
        entered = threading.Event()
        release = threading.Event()
        loop_thread = threading.get_ident()
        original = self.store.add_job

        def add_job(job):
            self.assertNotEqual(threading.get_ident(), loop_thread)
            entered.set()
            if not release.wait(2):
                raise AssertionError("bot event loop blocked by job store")
            return original(job)

        with patch.object(self.store, "add_job", side_effect=add_job):
            task = asyncio.create_task(self.tasks.schedule_reminder(1, "test", self.deadline))
            try:
                async def started():
                    while not entered.is_set():
                        await asyncio.sleep(0.001)
                await asyncio.wait_for(started(), 1)
                self.assertFalse(task.done())
            finally:
                release.set()
            await task

    async def test_due_job_polls_off_loop_but_runs_discord_callback_on_bot_loop(self):
        delivered = asyncio.Event()
        bot_loop = asyncio.get_running_loop()
        poll_threads = []
        original = self.store.get_due_jobs

        def get_due_jobs(now):
            poll_threads.append(threading.get_ident())
            return original(now)

        async def remind(*args):
            self.assertIs(asyncio.get_running_loop(), bot_loop)
            delivered.set()

        self.module.remind = remind
        with patch.object(self.store, "get_due_jobs", side_effect=get_due_jobs):
            await self.tasks.schedule_reminder(1, "test", datetime.now(timezone.utc))
            await self.tasks.resume()
            await asyncio.wait_for(delivered.wait(), 2)
        self.assertTrue(poll_threads)
        self.assertNotIn(threading.get_ident(), poll_threads)

    async def test_close_cancels_and_awaits_active_discord_callbacks(self):
        started = asyncio.Event()
        finished = asyncio.Event()

        async def remind(*args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()

        self.module.remind = remind
        await self.tasks.schedule_reminder(1, "test", datetime.now(timezone.utc))
        await self.tasks.resume()
        await asyncio.wait_for(started.wait(), 2)
        with self.assertLogs("apscheduler.executors.default", level="ERROR"):
            await self.tasks.close()
        self.assertTrue(finished.is_set())
        self.assertFalse(self.tasks._thread.is_alive())

    async def test_cancel_giveaway_handles_namespaced_and_legacy_ids(self):
        await self.tasks.schedule_end_giveaway(1, 10, self.deadline, 1)
        await self.tasks.cancel_giveaway(10)
        self.assertIsNone(self.scheduler.get_job("giveaway:10"))
        await self.tasks._call(self.scheduler.add_job, self.module.end_giveaway_callback,
                              'date', id="12", run_date=self.deadline, args=[1, 10, 1])
        await self.tasks.cancel_giveaway(10)
        self.assertIsNone(self.scheduler.get_job("12"))
