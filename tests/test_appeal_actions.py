"""Offline appeal workflow tests; Discord and database boundaries are mocked."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock


class HTTPException(Exception):
    pass


class NotFound(HTTPException):
    pass


class View:
    def __init__(self, **kwargs):
        self.children = [NS(disabled=False), NS(disabled=False)]


class Embed:
    def __init__(self):
        self.title = None
        self.description = 'Vote'
        self.footer = NS(text='Appeal applicant: 99')

    def copy(self):
        import copy
        return copy.deepcopy(self)


async def iterate(items):
    for item in items:
        yield item


def load_actions():
    path = Path(__file__).parents[1] / 'utils/views/appeal_actions.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    discord = NS(ui=NS(View=View, button=lambda **kw: lambda fn: fn),
                 ButtonStyle=NS(success=1, danger=2), HTTPException=HTTPException,
                 NotFound=NotFound, Object=lambda **kw: NS(**kw),
                 AllowedMentions=NS(none=lambda: None))
    env = dict(asyncio=asyncio, discord=discord, cfg=NS(ban_appeal_guild_id=1,
               ban_appeal_mod_role=10, guild_id=2, aaron_id=1), logger=Mock(),
               Case=lambda **kw: NS(**kw), guild_service=Mock(), user_service=Mock(),
               prepare_unban_log=Mock(return_value='log'))
    exec(compile(tree, str(path), 'exec'), env)
    return env


class AppealTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env = load_actions()
        self.cls = self.env['AppealActions']
        self.user = NS(id=99, send=AsyncMock())
        self.main = NS(unban=AsyncMock())
        self.bot = NS(user=NS(id=500), fetch_user=AsyncMock(return_value=self.user),
                      get_guild=Mock(return_value=self.main), ban_cache=Mock())
        self.members = [NS(id=i, bot=False, roles=[NS(id=10)]) for i in range(1, 5)]
        self.guild = NS(id=1, fetch_members=lambda **kw: iterate(self.members), kick=AsyncMock())
        self.message = NS(id=123, author=self.bot.user, embeds=[Embed()], reactions=[])
        async def edit(**kw):
            self.message.embeds = [kw['embed']]
        self.message.edit = AsyncMock(side_effect=edit)
        self.channel = NS(fetch_message=AsyncMock(return_value=self.message), send=AsyncMock())
        self.interaction = NS(guild=self.guild, channel=self.channel, message=self.message,
                              user=NS(id=2, mention='<@2>'), response=NS(defer=AsyncMock()),
                              followup=NS(send=AsyncMock()))

    def votes(self, up=(), down=(), abstain=()):
        class Reaction:
            def __init__(self, emoji, ids):
                self.emoji, self.ids = emoji, ids
            def users(self, **kwargs):
                return iterate([NS(id=i) for i in self.ids])
        self.message.reactions = [Reaction(e, ids) for e, ids in
                                 [('🔺', up), ('🔻', down), ('❌', abstain)]]

    def test_thresholds_and_conflicts(self):
        count = self.env['count_votes']
        self.assertEqual(count({1, 2, 3, 4}, {1, 2}, set(), set(), True), (2, 3))
        self.assertEqual(count({1, 2, 3, 4}, {1, 2}, set(), {4}, True), (2, 2))
        self.assertEqual(count({1, 2, 3}, {1, 2}, {2}, set(), True), (1, 2))
        self.assertEqual(count({1, 2}, {1, 9}, set(), {1}, True), (0, 1))
        self.assertEqual(count({1, 2}, set(), set(), {1, 2}, False), (0, 1))

    async def test_insufficient_majority(self):
        self.votes(up=[1, 2])
        await self.cls(self.bot)._resolve(self.interaction, True)
        self.main.unban.assert_not_awaited()
        self.message.edit.assert_not_awaited()
        self.assertIn("Majority hasn't", self.interaction.followup.send.call_args.args[0])

    async def test_approve_and_duplicate_after_restart(self):
        self.votes(up=[1, 2, 3, 500, 999])
        await self.cls(self.bot)._resolve(self.interaction, True)
        self.main.unban.assert_awaited_once()
        self.env['user_service'].add_case.assert_called_once()
        self.user.send.assert_awaited_once()
        self.assertIn('https://discord.gg/jb', self.user.send.call_args.args[0])
        self.guild.kick.assert_awaited_once()
        await self.cls(self.bot)._resolve(self.interaction, False)
        self.user.send.assert_awaited_once()
        self.assertTrue(all(c.disabled for c in self.message.edit.call_args.kwargs['view'].children))

    async def test_denial_does_not_unban_or_create_case(self):
        self.votes(down=[1, 2], abstain=[4])
        await self.cls(self.bot)._resolve(self.interaction, False)
        self.main.unban.assert_not_awaited()
        self.env['user_service'].add_case.assert_not_called()
        self.assertIn('denied', self.user.send.call_args.args[0])
        self.guild.kick.assert_awaited_once()

    async def test_failed_dm_keeps_member_and_provides_text(self):
        self.votes(up=[1, 2, 3])
        self.user.send.side_effect = HTTPException()
        await self.cls(self.bot)._resolve(self.interaction, True)
        self.guild.kick.assert_not_awaited()
        self.assertEqual(self.message.embeds[0].title, 'Appeal approved')
        self.assertIn('https://discord.gg/jb', self.channel.send.call_args.args[0])

    async def test_owner_override(self):
        self.interaction.user = NS(id=1, mention='<@1>')
        await self.cls(self.bot)._resolve(self.interaction, False)
        self.user.send.assert_awaited_once()
        self.assertIn('owner override', self.message.embeds[0].description)

    async def test_nonmoderator_cannot_override(self):
        self.members = self.members[1:]
        self.interaction.user = NS(id=1, mention='<@1>')
        await self.cls(self.bot)._resolve(self.interaction, False)
        self.user.send.assert_not_awaited()

    async def test_already_unbanned_does_not_duplicate_case(self):
        self.votes(up=[1, 2, 3])
        self.main.unban.side_effect = NotFound()
        await self.cls(self.bot)._resolve(self.interaction, True)
        self.env['user_service'].add_case.assert_not_called()
        self.user.send.assert_awaited_once()

    async def test_unban_failure_reopens_vote_without_dm(self):
        self.votes(up=[1, 2, 3])
        self.main.unban.side_effect = HTTPException()
        with self.assertRaises(HTTPException):
            await self.cls(self.bot)._resolve(self.interaction, True)
        self.assertIsNone(self.message.embeds[0].title)
        self.user.send.assert_not_awaited()

    async def test_concurrent_clicks_only_complete_once(self):
        self.votes(up=[1, 2, 3], down=[])
        view = self.cls(self.bot)
        await asyncio.gather(view.resolve(self.interaction, True), view.resolve(self.interaction, True))
        self.main.unban.assert_awaited_once()
        self.user.send.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
