import discord

from utils import format_number


def format_taglist_page(_, entries, current_page, all_pages):
    embed = discord.Embed(
        title=f'All tags', color=discord.Color.blurple())
    for tag in entries:
        desc = f"Added by: {tag.added_by_tag}\nUsed {format_number(tag.use_count)} times"
        if tag.image.read() is not None:
            desc += "\nHas image attachment"
        embed.add_field(name=tag.name, value=desc)
    embed.set_footer(
        text=f"Page {current_page} of {len(all_pages)}")
    return embed
