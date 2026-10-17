import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tests.support import load_module


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users = Mock()
        self.guilds = Mock()
        self.module = load_module("utils/jobs.py", {
            "utils": SimpleNamespace(cfg=SimpleNamespace(guild_id=123)),
            "data.services": SimpleNamespace(user_service=self.users, guild_service=self.guilds),
        })
        self.scheduler = AsyncIOScheduler(timezone=timezone.utc)
        self.scheduler.start(paused=True)
        self.tasks = self.module.Tasks.__new__(self.module.Tasks)
        self.tasks.tasks = self.scheduler
        self.deadline = datetime.now(timezone.utc) + timedelta(hours=1)

    async def asyncTearDown(self):
        self.scheduler.shutdown(wait=False)
        await asyncio.sleep(0)

    async def test_repeated_timeout_replaces_deadline(self):
        self.tasks.schedule_untimeout(1, self.deadline)
        later = self.deadline + timedelta(hours=1)
        self.tasks.schedule_untimeout(1, later)
        self.assertEqual(len(self.scheduler.get_jobs()), 1)
        self.assertEqual(self.scheduler.get_job("timeout:1").next_run_time, later)
        self.tasks.cancel_unmute(1)
        self.tasks.cancel_unmute(1)
        self.assertEqual(self.scheduler.get_jobs(), [])

    async def test_distinct_features_and_many_reminders_do_not_collide(self):
        self.tasks.schedule_untimeout(2, self.deadline)
        self.tasks.schedule_remove_bday(1, self.deadline)
        for _ in range(200):
            self.tasks.schedule_reminder(1, "test", self.deadline)
        self.assertEqual(len(self.scheduler.get_jobs()), 202)

    async def test_new_member_deadline_is_not_extended_by_messages(self):
        self.tasks.schedule_remove_new_member_role(1, self.deadline)
        self.tasks.schedule_remove_new_member_role(1, self.deadline + timedelta(hours=1))
        self.assertEqual(len(self.scheduler.get_jobs()), 1)
        self.assertEqual(self.scheduler.get_job("new-member:1").next_run_time, self.deadline)

    async def test_replacing_timeout_removes_matching_legacy_job(self):
        self.scheduler.add_job(self.module.untimeout_callback, 'date', id="1",
                               run_date=self.deadline, args=[1])
        self.tasks.schedule_untimeout(1, self.deadline)
        self.assertIsNone(self.scheduler.get_job("1"))
        self.assertIsNotNone(self.scheduler.get_job("timeout:1"))

    async def test_cancel_does_not_remove_other_feature_with_numeric_id(self):
        self.scheduler.add_job(self.module.remove_bday_callback, 'date', id="2",
                               run_date=self.deadline, args=[1])
        self.tasks.cancel_unmute(2)
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
        self.module.remind = AsyncMock(side_effect=RuntimeError("delivery failed"))
        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            await self.module.reminder_callback(1, "hello")
        self.module.remind.assert_awaited_once_with(1, "hello")
