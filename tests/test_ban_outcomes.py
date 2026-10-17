from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from tests.support import load_module


class BanOutcomeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users = Mock()
        guilds = Mock()
        guilds.allocate_case_id.return_value = 42
        self.module = load_module("utils/mod/modactions_helpers.py", {
            "data.services.guild_service": SimpleNamespace(guild_service=guilds),
            "data.services.user_service": SimpleNamespace(user_service=self.users),
            "utils.context": Mock(), "utils.mod.mod_logs": Mock(), "utils.config": Mock(),
        })
        self.bot = Mock()
        self.guild = Mock(ban=AsyncMock())
        self.member = SimpleNamespace(id=1)
        self.mod = SimpleNamespace(id=2)

    async def test_failed_ban_does_not_create_case_or_poison_cache(self):
        self.guild.ban.side_effect = RuntimeError("missing permission")
        with self.assertRaises(RuntimeError):
            await self.module.execute_ban(self.bot, self.guild, self.member, self.mod, "reason")
        self.users.add_case.assert_not_called()
        self.bot.ban_cache.ban.assert_not_called()

    async def test_case_is_recorded_only_after_discord_accepts_ban(self):
        async def ban(*args, **kwargs):
            self.users.add_case.assert_not_called()
            self.bot.ban_cache.ban.assert_not_called()
        self.guild.ban.side_effect = ban
        await self.module.execute_ban(self.bot, self.guild, self.member, self.mod, "reason")
        self.users.add_case.assert_called_once()
        self.bot.ban_cache.ban.assert_called_once_with(1)
        self.assertEqual(self.guild.ban.call_args.kwargs["reason"], "reason")
