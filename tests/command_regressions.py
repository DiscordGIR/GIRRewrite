"""Exercise reported command failures inside the isolated boot fixture."""
import asyncio
from datetime import datetime, timezone
import inspect
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.ext import commands
from data.model import Cases, Case, Tag
from tests.boot_smoke import check


async def assertions(bot):
    from cogs.commands.info import userinfo
    from cogs.commands.misc import giveaway, memes
    from cogs.commands.mod.modactions import ModActions
    from cogs.commands.misc.genius_submod import Genius
    from data.services.user_service import _repository
    from utils.views.misc import PFPView
    from utils.views.modals.tag import TagModal, EditTagModal

    ctx = NS(guild=NS(get_member=lambda uid: NS(mention=f'<@{uid}>', display_avatar='https://example.com/avatar.png')),
             whisper=True, send_warning=AsyncMock())
    with patch.object(userinfo.user_service, 'leaderboard', AsyncMock(return_value=[])):
        await inspect.unwrap(userinfo.UserInfo.xptop.callback)(NS(), ctx)
    ctx.send_warning.assert_awaited_once()
    for size in (1, 2, 3):
        entries = [(i, NS(_id=i, level=1)) for i in range(size)]
        embed = userinfo.format_xptop_page(ctx, entries, 1, [entries])
        assert len(embed.fields) == size
        assert ':first_place:' in embed.fields[0].value
    # Database rank must be assigned after filtering users outside the guild.
    ctx.guild.get_member = lambda uid: None if uid == 99 else NS()
    with patch.object(userinfo.user_service, 'leaderboard', AsyncMock(return_value=[NS(_id=99), NS(_id=1)])), patch.object(userinfo, 'Menu') as menu:
        menu.return_value.start = AsyncMock()
        await inspect.unwrap(userinfo.UserInfo.xptop.callback)(NS(), ctx)
        assert menu.call_args.args[1][0][0] == 0

    case = Case(_id=501, _type='MUTE', date=datetime(2026, 11, 6, 20, 15),
                mod_id=2, mod_tag='mod', reason='QA MiXeD', punishment='20 seconds')
    ctx.case_user = NS(display_avatar='https://example.com/avatar.png')
    ctx.case_profile = NS(warn_points=0)
    embed = userinfo.format_cases_page(ctx, [case], 1, [[case]])
    expected = int(case.date.replace(tzinfo=timezone.utc).timestamp())
    assert f'<t:{expected}:F>' in embed.fields[0].value
    Cases(_id=501, cases=[case]).save()
    result = _repository.fetch_cases_by_keyword('qa mixed')
    assert result['total'] == 1
    assert _repository.fetch_cases_by_keyword('QA MIXED')['total'] == 1
    assert _repository.fetch_cases_by_keyword('unmatched')['total'] == 0

    for value in ('bad-id', '0', '-1'):
        for command in (giveaway.Giveaway.end, giveaway.Giveaway.reroll):
            with_error = False
            try:
                await inspect.unwrap(command.callback)(NS(), NS(), value)
            except commands.BadArgument:
                with_error = True
            assert with_error
    assert giveaway.parse_giveaway_id('123') == 123

    author = NS(id=1)
    for modal in (TagModal(bot, 'qatag', author), EditTagModal(Tag(name='qatag', content='old'), author)):
        modal.children[0]._value = 'new body'
        interaction = NS(user=author, response=NS(defer=AsyncMock()))
        await modal.on_submit(interaction)
        interaction.response.defer.assert_awaited_once()
        assert modal.is_finished()
        assert modal.tag.content == 'new body'

    view_ctx = NS(respond_or_edit=AsyncMock())
    view = PFPView(view_ctx)
    await view.on_timeout()
    assert 'embed' not in view_ctx.respond_or_edit.call_args.kwargs
    original = discord.Embed(title='avatar')
    view = PFPView(view_ctx, original)
    await view.on_timeout()
    assert view_ctx.respond_or_edit.call_args.kwargs['embed'] is original

    response = NS(id=4)
    channel = NS(purge=AsyncMock(return_value=[NS(id=i) for i in range(3)]))
    purge_ctx = NS(defer=AsyncMock(), channel=channel, interaction=NS(original_response=AsyncMock(return_value=response)), send_success=AsyncMock())
    await inspect.unwrap(ModActions.purge.callback)(NS(), purge_ctx, 3)
    channel.purge.assert_awaited_once_with(limit=3, before=response)
    assert 'Purged 3' in purge_ctx.send_success.call_args.args[0]

    # The offline bot has no gateway user; supply an explicit identity.
    cog = Genius(NS(user=NS(id=42), issue_cache=NS(cache={})))
    async def issue_history(**kwargs):
        yield NS(author=NS(id=42), embeds=[NS(footer=NS(text='Submitted by QA'), title='One issue')], jump_url='https://example.com/issue')
    count, pages = await cog.do_reindex(NS(history=issue_history, send=AsyncMock()))
    assert (count, pages) == (1, 1)
    assert 'RESNEXT_TOKEN' in memes.meme_service_error(401)
    assert 'HTTP 503' in memes.meme_service_error(503)


if __name__ == '__main__':
    asyncio.run(check(assertions))
