from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from tests.support import load_module


class TimeoutOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        helpers = SimpleNamespace(execute_ban=AsyncMock(), notify_user=AsyncMock(),
                                  notify_user_warn=AsyncMock(), response_log=AsyncMock(),
                                  submit_public_log=AsyncMock())
        self.services = SimpleNamespace(guild_service=AsyncMock(), user_service=AsyncMock())
        self.services.guild_service.allocate_case_id.return_value = 1
        self.module = load_module("utils/mod/global_modactions.py", {
            "utils": SimpleNamespace(cfg=Mock(), logger=Mock()),
            "data.services": self.services,
            "utils.mod.mod_logs": Mock(),
            "utils.mod.modactions_helpers": helpers,
        }, module_name="utils.mod.global_modactions")
        self.module.unmute = AsyncMock()
        self.deadline = datetime.now(timezone.utc) + timedelta(days=1)
        self.member = SimpleNamespace(timed_out_until=self.deadline)
        self.ctx = SimpleNamespace(guild=SimpleNamespace(fetch_member=AsyncMock(return_value=self.member)),
                                   user=Mock())

    async def test_dismiss_removes_its_own_timeout(self):
        await self.module.dismiss_report_timeout(self.ctx, 1, self.deadline, "dismiss")
        self.module.unmute.assert_awaited_once()

    async def test_dismiss_preserves_newer_timeout(self):
        self.member.timed_out_until += timedelta(hours=1)
        with self.assertRaises(ValueError):
            await self.module.dismiss_report_timeout(self.ctx, 1, self.deadline, "dismiss")
        self.module.unmute.assert_not_called()

    async def test_report_without_successful_timeout_cannot_unmute(self):
        await self.module.dismiss_report_timeout(self.ctx, 1, None, "dismiss")
        self.ctx.guild.fetch_member.assert_not_called()
        self.module.unmute.assert_not_called()

    async def test_scheduler_failure_does_not_erase_successful_mute(self):
        member = Mock(id=1, timeout=AsyncMock())
        ctx = Mock()
        ctx.bot.tasks.schedule_untimeout = AsyncMock(side_effect=RuntimeError("database unavailable"))
        mod = SimpleNamespace(id=2)
        deadline = await self.module.mute(ctx, member, mod, dur_seconds=60)
        self.assertIsNotNone(deadline)
        self.services.user_service.add_case.assert_called_once()

    async def test_failed_discord_timeout_propagates_without_case(self):
        member = Mock(id=1, timeout=AsyncMock(side_effect=RuntimeError("forbidden")))
        with self.assertRaises(RuntimeError):
            await self.module.mute(Mock(), member, SimpleNamespace(id=2), dur_seconds=60)
        self.services.user_service.add_case.assert_not_called()
