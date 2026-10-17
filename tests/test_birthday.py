from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from tests.support import load_module


class BirthdayTests(unittest.IsolatedAsyncioTestCase):
    async def test_departed_member_does_not_skip_remaining_birthdays(self):
        grant = AsyncMock()
        users = Mock()
        users.retrieve_birthdays.return_value = [
            SimpleNamespace(_id=1, birthday_excluded=False),
            SimpleNamespace(_id=2, birthday_excluded=False),
        ]
        module = load_module("cogs/monitors/utils/birthday.py", {
            "data.services": SimpleNamespace(user_service=users, guild_service=Mock()),
            "utils": SimpleNamespace(GIRContext=Mock(), cfg=Mock()),
            "utils.framework": SimpleNamespace(MONTH_MAPPING={}, give_user_birthday_role=grant,
                                               whisper=Mock(), gatekeeper=Mock()),
            "utils.views": SimpleNamespace(date_autocompleter=Mock()),
        })
        member = Mock()
        guild = Mock()
        guild.get_member.side_effect = [None, member]

        async def run(function):
            return function()

        cog = module.Birthday.__new__(module.Birthday)
        cog.bot = Mock()
        cog.bot.database_io.run = run
        cog.bot.get_guild.return_value = guild
        await module.Birthday.birthday.coro(cog)
        grant.assert_awaited_once_with(cog.bot, member, guild)
