"""Exercise giveaway and issue-index boundaries without network or credentials."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.ext import commands
from tests.support import load_module


def identity(value):
    return value


async def autocomplete(interaction, current):
    return []


def load_cog(path):
    return load_module(path, {
        'utils': NS(GIRContext=type('Context', (), {}), cfg=NS(guild_id=123),
                    end_giveaway=AsyncMock(), transform_context=identity),
        'utils.context': NS(transform_context=identity),
        'utils.framework': NS(admin_and_up=lambda: identity, genius_or_submod_and_up=lambda: identity,
                              submod_or_admin_and_up=lambda: identity, whisper_in_general=identity,
                              ImageAttachment=discord.Attachment, gatekeeper=Mock()),
        'utils.framework.transformers': NS(Duration=float),
        'utils.views': NS(time_suggestions=autocomplete, issue_autocomplete=autocomplete,
                          CommonIssueModal=Mock(), EditCommonIssue=Mock(), GenericDescriptionModal=Mock()),
        'data.services': NS(guild_service=NS(get_giveaway=AsyncMock())),
    })


class RerollTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module = load_cog('cogs/commands/misc/giveaway.py')
        self.channel = NS(send=AsyncMock())
        self.members = {2: NS(id=2, mention='<@2>'), 3: NS(id=3, mention='<@3>')}
        self.ctx = NS(guild=NS(get_member=Mock(side_effect=self.members.get),
                              get_channel=lambda _: self.channel), send_success=AsyncMock())
        self.giveaway = NS(is_ended=True, name='prize', entries=[], previous_winners=[],
                           channel=10, save=Mock())
        self.module.guild_service.get_giveaway.return_value = self.giveaway
        async def database(function):
            return function()
        self.module.run_database = database

    async def reroll(self):
        await self.module.Giveaway.reroll.callback(NS(), self.ctx, '123')

    async def test_all_remaining_departed(self):
        self.giveaway.entries = [1, 2]
        self.giveaway.previous_winners = [2]
        with self.assertRaisesRegex(commands.BadArgument, 'No more winners'):
            await self.reroll()
        self.giveaway.save.assert_not_called()

    async def test_all_already_won(self):
        self.giveaway.entries = [2, 3]
        self.giveaway.previous_winners = [2, 3]
        with self.assertRaisesRegex(commands.BadArgument, 'No more winners'):
            await self.reroll()

    async def test_single_survivor_and_duplicate_ids(self):
        self.giveaway.entries = [1, 2, 2, 3, 3]
        self.giveaway.previous_winners = [3]
        with patch.object(self.module.random, 'choice', side_effect=lambda values: values[0]) as choose:
            await self.reroll()
        self.assertEqual(choose.call_args.args[0], [self.members[2]])
        choose.assert_called_once()
        self.assertEqual(self.giveaway.previous_winners, [3, 2])
        self.giveaway.save.assert_called_once()
        self.channel.send.assert_awaited_once()

    async def test_empty_entries_preserve_error(self):
        with self.assertRaisesRegex(commands.BadArgument, 'There are no entries'):
            await self.reroll()

    async def test_invalid_ids_preserve_error(self):
        for value in ['bad-id', '0', '-1']:
            with self.assertRaisesRegex(commands.BadArgument, 'Invalid giveaway message ID'):
                await self.module.Giveaway.reroll.callback(NS(), self.ctx, value)


class GiveawayEndTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = NS(get_giveaway=AsyncMock())
        self.module = load_module('utils/jobs.py', {
            'utils': NS(cfg=NS(guild_id=123)),
            'data.services': NS(guild_service=self.service, user_service=AsyncMock()),
        })
        self.members = {2: NS(id=2, mention='<@2>'), 3: NS(id=3, mention='<@3>')}
        embed = discord.Embed(title='Prize')
        embed.add_field(name='Time remaining', value='Soon')
        self.message = NS(id=100, embeds=[embed], reactions=[], edit=AsyncMock(), clear_reactions=AsyncMock())
        self.channel = NS(fetch_message=AsyncMock(return_value=self.message), send=AsyncMock())
        self.guild = NS(get_member=Mock(side_effect=self.members.get), get_channel=lambda _: self.channel)
        self.module.BOT_GLOBAL = NS(user=NS(id=42), get_guild=lambda _: self.guild)
        self.giveaway = NS(name='prize', sponsor=8, save=Mock())
        self.service.get_giveaway.return_value = self.giveaway
        async def database(function):
            return function()
        self.module.run_database = database

    def reaction(self, emoji, ids):
        async def users():
            for member_id in ids:
                yield NS(id=member_id)
        return NS(emoji=emoji, users=users)

    async def test_missing_reactions_finish_without_winners(self):
        await self.module.end_giveaway(1, 100, 2)
        self.assertEqual(self.giveaway.entries, [])
        self.assertEqual(self.giveaway.previous_winners, [])
        self.assertTrue(self.giveaway.is_ended)
        self.giveaway.save.assert_called_once()

    async def test_entry_emoji_not_first_and_bot_reaction_absent(self):
        self.message.reactions = [self.reaction('👍', [3]), self.reaction('🎉', [1, 2, 2])]
        await self.module.end_giveaway(1, 100, 5)
        self.assertEqual(self.giveaway.entries, [1, 2])
        self.assertEqual(self.giveaway.previous_winners, [2])
        self.assertIn('<@2>', self.channel.send.call_args.args[0])

    async def test_own_bot_excluded_and_winner_count_capped(self):
        self.message.reactions = [self.reaction('🎉', [42, 1, 2, 3])]
        with patch.object(self.module.random, 'sample', side_effect=lambda values, count: values[:count]) as sample:
            await self.module.end_giveaway(1, 100, 1)
        self.assertEqual(self.giveaway.entries, [1, 2, 3])
        self.assertEqual(self.giveaway.previous_winners, [2])
        sample.assert_called_once_with([self.members[2], self.members[3]], 1)

    async def test_all_departed_finish_without_sampling_loop(self):
        self.message.reactions = [self.reaction('🎉', [1, 9])]
        await self.module.end_giveaway(1, 100, 2)
        self.assertEqual(self.giveaway.entries, [1, 9])
        self.assertEqual(self.giveaway.previous_winners, [])
        self.assertIn('no eligible entrants', self.channel.send.call_args.args[0])


class IssuePaginationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module = load_cog('cogs/commands/misc/genius_submod.py')
        self.bot = NS(user=NS(id=42), issue_cache=NS(cache={'old': 'preserved'}))
        self.cog = self.module.Genius(self.bot)
        self.old_index = NS(author=NS(id=42),
                            embeds=[NS(footer=NS(text='Table of Contents • Page 1'))],
                            delete=AsyncMock())
        self.messages = [self.old_index]
        self.sent = []
        async def history(**kwargs):
            for message in self.messages:
                yield message
        async def send(*, embed):
            self.sent.append(embed.copy())
        self.channel = NS(history=history, send=AsyncMock(side_effect=send))

    def issue(self, title, url):
        return NS(author=NS(id=42),
                  embeds=[NS(footer=NS(text='Submitted by QA'), title=title)],
                  jump_url=url)

    async def test_multiple_overflows_preserve_every_link_once_in_order(self):
        issues = [self.issue(f'Issue {i}: ' + 'x' * 240, f'https://example.com/issues/{i:03d}')
                  for i in range(50)]
        self.messages.extend(issues)
        count, pages = await self.cog.do_reindex(self.channel)
        self.assertEqual(count, 50)
        self.assertGreater(pages, 2)
        self.assertEqual(pages, len(self.sent))
        joined = ''.join(embed.description for embed in self.sent)
        positions = []
        for index, issue in enumerate(issues, start=1):
            self.assertEqual(joined.count(issue.jump_url), 1)
            self.assertIn(f'{index}. [{issue.embeds[0].title}]({issue.jump_url})', joined)
            positions.append(joined.index(issue.jump_url))
        self.assertEqual(positions, sorted(positions))
        self.assertTrue(all(len(embed.description) <= 4096 for embed in self.sent))
        self.old_index.delete.assert_awaited_once()
        self.assertEqual(len(self.bot.issue_cache.cache), 50)

    async def test_exact_boundary_stays_on_same_page(self):
        prefix = 'Click on a link to jump to the issue!\n'
        url = 'https://example.com/exact'
        overhead = len(f'\n1. []({url})')
        title = 'x' * (4096 - len(prefix) - overhead)
        self.messages.append(self.issue(title, url))
        self.assertEqual(await self.cog.do_reindex(self.channel), (1, 1))
        self.assertEqual(len(self.sent[0].description), 4096)

    async def test_overflow_entry_starts_next_page(self):
        prefix = 'Click on a link to jump to the issue!\n'
        url = 'https://example.com/first'
        title = 'x' * (4096 - len(prefix) - len(f'\n1. []({url})'))
        self.messages.extend([self.issue(title, url), self.issue('Second', 'https://example.com/second')])
        self.assertEqual(await self.cog.do_reindex(self.channel), (2, 2))
        self.assertEqual(self.sent[1].description, '\n2. [Second](https://example.com/second)')

    async def test_oversized_title_or_link_keeps_existing_index(self):
        for title, url in [('x' * 4096, 'https://example.com/a'), ('Small', 'https://example.com/' + 'x' * 4096)]:
            with self.subTest(kind='title' if len(title) > 100 else 'url'):
                self.messages = [self.old_index, self.issue('Valid first', 'https://example.com/valid'),
                                 self.issue(title, url)]
                with self.assertRaisesRegex(commands.BadArgument, 'too long'):
                    await self.cog.do_reindex(self.channel)
                self.old_index.delete.assert_not_awaited()
                self.channel.send.assert_not_awaited()
                self.assertEqual(self.bot.issue_cache.cache, {'old': 'preserved'})

    async def test_empty_index_retains_intro_page(self):
        self.assertEqual(await self.cog.do_reindex(self.channel), (0, 1))
        self.assertIn('Click on a link', self.sent[0].description)
