from typing import List

import discord

from core.domain import LeaderboardEntry
from utils import GIRContext


def format_xptop_page(ctx: GIRContext, entries: List[LeaderboardEntry], current_page: int, all_pages: List[List[LeaderboardEntry]]) -> discord.Embed:
    """Formats the page for the xptop embed.

    Parameters
    ----------
    ctx: GIRContext
        "The context of the command"
    entries: list
        "The entries that we will display on this page"
    current_page : number
        "The number of the page that we are currently on"
    all_pages : list
        "All entries that we will eventually iterate through, batched"

    Returns
    -------
    discord.Embed
        "The embed that we will send"

    """
    embed = discord.Embed(title=f'Leaderboard', color=discord.Color.blurple())
    for entry in entries:
        member = ctx.guild.get_member(entry.user_id)
        trophy = ''
        match entry.rank:
            case 1:
                trophy = ':first_place:'
                embed.set_thumbnail(url=member.avatar)
            case 2:
                trophy = ':second_place:'
            case 3:
                trophy = ':third_place:'
            case _:
                pass

        embed.add_field(name=f"#{entry.rank} - Level {entry.level}",
                        value=f"{trophy} {member.mention}", inline=False)

    embed.set_footer(text=f"Page {current_page} of {len(all_pages)}")
    return embed
