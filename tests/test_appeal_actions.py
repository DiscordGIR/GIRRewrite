"""Offline appeal tests; replace startup/database imports, keep real Discord views."""
import asyncio
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

cfg = NS(ban_appeal_guild_id=10, ban_appeal_mod_role=20, guild_id=30,
         aaron_id=40, owner_id=50, channels=NS(public_logs=60))
services = NS(guild_service=Mock(), user_service=Mock())
dependencies = {
    'data.model': NS(Case=Mock()),
    'data.services': services,
    'utils': NS(cfg=cfg, logger=Mock()),
    'utils.mod.mod_logs': NS(prepare_unban_log=Mock()),
    'utils.mod.modactions_helpers': NS(submit_public_log=AsyncMock()),
}
spec = importlib.util.spec_from_file_location(
    'appeal_actions_under_test', Path(__file__).resolve().parents[1] / 'utils/views/appeal_actions.py')
appeals = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, dependencies):
    spec.loader.exec_module(appeals)


async def items(values):
    for value in values:
        yield value


class AppealTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = NS(id=99, mention='<@99>', send=AsyncMock())
        self.channel = NS(id=70, send=AsyncMock(), edit=AsyncMock(), fetch_message=AsyncMock())
        self.main = NS(unban=AsyncMock(), get_channel=Mock(return_value=object()), name='Main')
        self.bot = NS(user=NS(id=100), fetch_user=AsyncMock(return_value=self.user),
                      get_guild=Mock(return_value=self.main), get_channel=Mock(return_value=self.channel),
                      ban_cache=NS(unban=Mock()))
        self.actions = appeals.AppealActions(self.bot)
        self.members = [NS(id=i, bot=False, roles=[NS(id=20)]) for i in (1, 2, 3)]
        self.guild = NS(id=10, fetch_members=lambda **kw: items(self.members), kick=AsyncMock())
        self.message = NS(id=80, guild=self.guild, channel=self.channel, author=self.bot.user,
                          embeds=[discord.Embed(description='Vote')], reactions=[],
                          components=[NS(children=[NS(custom_id='unban_appeal:approve:99')])])

        async def edit(**kwargs):
            self.message.embeds = [kwargs['embed'].copy()]
        self.message.edit = AsyncMock(side_effect=edit)
        self.channel.fetch_message.return_value = self.message
        self.payload = NS(guild_id=10, channel_id=70, message_id=80, user_id=1, emoji='🔺')

    def votes(self, up=(), down=(), abstain=()):
        self.message.reactions = [NS(emoji=emoji, users=lambda limit, ids=ids: items([NS(id=i) for i in ids]))
                                  for emoji, ids in [('🔺', up), ('🔻', down), ('❌', abstain)]]

    def interaction(self, user_id):
        return NS(guild=self.guild, user=NS(id=user_id), channel=self.channel, message=self.message,
                  response=NS(defer=AsyncMock()), followup=NS(send=AsyncMock()),
                  delete_original_response=AsyncMock())

    async def test_majority_automatically_unbans_and_records_bot_actor(self):
        self.votes(up=(1, 2))
        await self.actions.handle_reaction(self.payload)
        self.main.unban.assert_awaited_once()
        self.assertEqual(appeals.Case.call_args.kwargs['mod_id'], self.bot.user.id)
        self.assertEqual(self.message.embeds[0].title, 'Appeal approved')
        self.user.send.assert_awaited_once()
        self.guild.kick.assert_awaited_once()
        self.channel.edit.assert_awaited_once_with(archived=True, locked=True)

    async def test_majority_automatically_denies(self):
        self.votes(down=(1, 2))
        await self.actions.handle_reaction(self.payload)
        self.main.unban.assert_not_awaited()
        self.assertEqual(self.message.embeds[0].title, 'Appeal denied')
        self.user.send.assert_awaited_once()

    async def test_no_majority_does_nothing(self):
        self.votes(up=(1, 999), down=(2,))
        await self.actions.handle_reaction(self.payload)
        self.message.edit.assert_not_awaited()
        self.bot.fetch_user.assert_not_awaited()

    async def test_abstentions_reduce_threshold(self):
        self.votes(up=(1,), abstain=(2, 3))
        await self.actions.handle_reaction(self.payload)
        self.main.unban.assert_awaited_once()

    async def test_dual_votes_do_not_support_either_outcome(self):
        self.votes(up=(1, 2), down=(2,))
        await self.actions.handle_reaction(self.payload)
        self.message.edit.assert_not_awaited()

    async def test_simultaneous_events_resolve_once(self):
        self.votes(up=(1, 2))
        await asyncio.gather(*(self.actions.handle_reaction(self.payload) for _ in range(3)))
        self.main.unban.assert_awaited_once()
        self.user.send.assert_awaited_once()

    async def test_moderator_cannot_press_override_even_with_majority(self):
        self.votes(up=(1, 2))
        interaction = self.interaction(1)
        await self.actions.resolve(interaction, 99, True)
        self.main.unban.assert_not_awaited()
        self.assertIn('Only the server owner', interaction.followup.send.call_args.args[0])

    async def test_owners_can_override_without_moderator_role_or_votes(self):
        for owner_id in (cfg.aaron_id, cfg.owner_id):
            with self.subTest(owner_id=owner_id):
                self.message.embeds = [discord.Embed(description='Vote')]
                await self.actions.resolve(self.interaction(owner_id), 99, False)
                self.assertEqual(self.message.embeds[0].title, 'Appeal denied')
                self.assertIn('Owner override used', self.message.embeds[0].description)

    async def test_spoofed_messages_ignored(self):
        self.message.author = NS(id=999)
        self.votes(up=(1, 2))
        await self.actions.handle_reaction(self.payload)
        self.main.unban.assert_not_awaited()

    async def test_failed_unban_reopens_vote(self):
        self.votes(up=(1, 2))
        self.main.unban.side_effect = discord.HTTPException(NS(status=403, reason='Forbidden'), 'error')
        await self.actions.handle_reaction(self.payload)
        self.assertIsNone(self.message.embeds[0].title)
        self.user.send.assert_not_awaited()
        self.guild.kick.assert_not_awaited()

    async def test_failed_dm_keeps_applicant_and_thread_open(self):
        self.votes(down=(1, 2))
        self.user.send.side_effect = discord.HTTPException(NS(status=403, reason='Forbidden'), 'error')
        await self.actions.handle_reaction(self.payload)
        self.assertEqual(self.message.embeds[0].title, 'Appeal denied')
        self.guild.kick.assert_not_awaited()
        self.channel.edit.assert_not_awaited()

    async def test_override_labels_and_persistent_ids(self):
        view = self.actions.create_view(99)
        self.assertTrue(all(button.label.startswith('Owner override:') for button in view.children))
        self.assertEqual(view.children[0].custom_id, 'unban_appeal:approve:99')


if __name__ == '__main__':
    unittest.main()
