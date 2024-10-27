from typing import List

import discord
from discord.utils import format_dt

from core.domain import determine_emoji, pun_map, CaseResult
from core.model import CaseType
from utils import GIRContext


def format_cases_page(ctx: GIRContext, entries: List[CaseResult], current_page: int, all_pages: List[List[CaseResult]]) -> discord.Embed:
    """Formats the page for the cases embed.

    Parameters
    ----------
    entry : dict
        "The dictionary for the entry"
    all_pages : list
        "All entries that we will eventually iterate through"
    current_page : number
        "The number of the page that we are currently on"

    Returns
    -------
    discord.Embed
        "The embed that we will send"

    """

    page_count = 0

    user = ctx.target
    warn_points = entries[0].warn_points

    page_count = sum(len(page) for page in all_pages)

    embed = discord.Embed(
        title=f'Cases - {warn_points} warn points', color=discord.Color.blurple())
    embed.set_author(name=user, icon_url=user.display_avatar)

    for case in entries:
        timestamp = case.date
        formatted = f"{format_dt(timestamp, style='F')} ({format_dt(timestamp, style='R')})"
        if case.case_type == "WARN" or case.case_type == CaseType.LIFTWARN:
            if case.lifted:
                embed.add_field(name=f'{determine_emoji(case.case_type)} Case #{case.case_id} [LIFTED]',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Lifted by**: {case.lifted_by_tag}\n**Lift reason**: {case.lifted_reason}\n**Warned on**: {formatted}',
                                inline=True)
            elif case.case_type == CaseType.LIFTWARN:
                embed.add_field(name=f'{determine_emoji(case.case_type)} Case #{case.case_id} [LIFTED (legacy)]',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Warned on**: {formatted}',
                                inline=True)
            else:
                embed.add_field(name=f'{determine_emoji(case.case_type)} Case #{case.case_id}',
                                value=f'**Points**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Warned on**: {formatted}',
                                inline=True)
        elif case.case_type == "MUTE" or case.case_type == CaseType.REMOVEPOINTS:
            embed.add_field(name=f'{determine_emoji(case.case_type)} Case #{case.case_id}',
                            value=f'**{pun_map[case.case_type]}**: {case.punishment}\n**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Time**: {formatted}',
                            inline=True)
        elif case.case_type in pun_map:
            embed.add_field(name=f'{determine_emoji(case.case_type)} Case #{case.case_id}',
                            value=f'**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**{pun_map[case.case_type]} on**: {formatted}',
                            inline=True)
        else:
            embed.add_field(name=f'{determine_emoji(case.case_type)} Case #{case.case_id}',
                            value=f'**Reason**: {case.reason}\n**Moderator**: {case.mod_tag}\n**Time**: {formatted}',
                            inline=True)
    embed.set_footer(
        text=f"Page {current_page} of {len(all_pages)} - newest cases first ({page_count} total cases)")
    return embed
