import re
from datetime import datetime
from io import BytesIO

import discord
from data.model.tag import Tag
from data.services.guild_service import guild_service
from discord import app_commands
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping
from utils import BlooContext, cfg
from utils.context import transform_context
from utils.framework import (MessageTextBucket, gatekeeper,
                             genius_or_submod_and_up, whisper, ImageAttachment)
from utils.views import Menu, tags_autocomplete, EditTagModal, TagModal



def format_tag_page(_, entries, current_page, all_pages):
    embed = discord.Embed(
        title=f'All tags', color=discord.Color.blurple())
    for tag in entries:
        desc = f"Added by: {tag.added_by_tag}\nUsed {tag.use_count} times"
        if tag.image.read() is not None:
            desc += "\nHas image attachment"
        embed.add_field(name=tag.name, value=desc)
    embed.set_footer(
        text=f"Page {current_page} of {len(all_pages)}")
    return embed


def prepare_tag_embed(tag):
    """Given a tag object, prepare the appropriate embed for it

    Parameters
    ----------
    tag : Tag
        Tag object from database

    Returns
    -------
    discord.Embed
        The embed we want to send
    """
    embed = discord.Embed(title=tag.name)
    embed.description = tag.content
    embed.timestamp = tag.added_date
    embed.color = discord.Color.blue()

    if tag.image.read() is not None:
        embed.set_image(url="attachment://image.gif" if tag.image.content_type ==
                        "image/gif" else "attachment://image.png")
    embed.set_footer(
        text=f"Added by {tag.added_by_tag} | Used {tag.use_count} times")
    return embed


def prepare_tag_view(tag: Tag):
    if not tag.button_links or tag.button_links is None:
        return discord.utils.MISSING

    view = discord.ui.View()
    for label, link in tag.button_links:
        # regex match emoji in label
        custom_emojis = re.search(
            r'<:\d+>|<:.+?:\d+>|<a:.+:\d+>|[\U00010000-\U0010ffff]', label)
        if custom_emojis is not None:
            emoji = custom_emojis.group(0).strip()
            label = label.replace(emoji, '')
            label = label.strip()
        else:
            emoji = None
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link, label=label, url=link, emoji=emoji))

    return view


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tag_cooldown = CooldownMapping.from_cooldown(
            1, 5, MessageTextBucket.custom)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Display a tag")
    @app_commands.describe(name="Name of the tag to display")
    @app_commands.describe(user_to_mention="Member to ping in response")
    @app_commands.autocomplete(name=tags_autocomplete)
    @transform_context
    async def tag(self, ctx: BlooContext, name: str, user_to_mention: discord.Member = None):
        name = name.lower()
        tag = guild_service.get_tag(name)

        if tag is None:
            raise commands.BadArgument("That tag does not exist.")

        # run cooldown so tag can't be spammed
        bucket = self.tag_cooldown.get_bucket(tag.name)
        current = datetime.now().timestamp()
        # ratelimit only if the invoker is not a moderator
        if bucket.update_rate_limit(current) and not (gatekeeper.has(ctx.guild, ctx.author, 5) or ctx.guild.get_role(guild_service.get_guild().role_sub_mod) in ctx.author.roles):
            raise commands.BadArgument("That tag is on cooldown.")

        # if the Tag has an image, add it to the embed
        _file = tag.image.read()
        if _file is not None:
            _file = discord.File(BytesIO(
                _file), filename="image.gif" if tag.image.content_type == "image/gif" else "image.png")
        else:
            _file = discord.utils.MISSING

        if user_to_mention is not None:
            title = f"Hey {user_to_mention.mention}, have a look at this!"
        else:
            title = None

        await ctx.respond(content=title, embed=prepare_tag_embed(tag), view=prepare_tag_view(tag), file=_file)

    @commands.guild_only()
    @commands.command(name="tag", aliases=["t"])
    async def _tag(self, ctx: commands.Context, name: str):
        name = name.lower()
        tag = guild_service.get_tag(name)

        if tag is None:
            raise commands.BadArgument("That tag does not exist.")

        # run cooldown so tag can't be spammed
        bucket = self.tag_cooldown.get_bucket(tag.name)
        current = datetime.now().timestamp()
        # ratelimit only if the invoker is not a moderator
        if bucket.update_rate_limit(current) and not (gatekeeper.has(ctx.guild, ctx.author, 5) or ctx.guild.get_role(guild_service.get_guild().role_sub_mod) in ctx.author.roles):
            raise commands.BadArgument("That tag is on cooldown.")

        # if the Tag has an image, add it to the embed
        _file = tag.image.read()
        if _file is not None:
            _file = discord.File(BytesIO(
                _file), filename="image.gif" if tag.image.content_type == "image/gif" else "image.png")
        else:
            _file = discord.utils.MISSING

        if ctx.message.reference is not None:
            title = f"Hey {ctx.message.reference.resolved.author.mention}, have a look at this!"
            await ctx.send(content=title, embed=prepare_tag_embed(tag), view=prepare_tag_view(tag), file=_file)
        else:
            await ctx.message.reply(embed=prepare_tag_embed(tag), view=prepare_tag_view(tag), file=_file, mention_author=False)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="List all tags")
    @transform_context
    @whisper
    async def taglist(self, ctx: BlooContext):
        _tags = sorted(guild_service.get_guild().tags, key=lambda tag: tag.name)

        if len(_tags) == 0:
            raise commands.BadArgument("There are no tags defined.")

        menu = Menu(ctx, _tags, per_page=12, page_formatter=format_tag_page, whisper=ctx.whisper)
        await menu.start()

    tags = app_commands.Group(name="tags", description="Interact with tags", guild_ids=[cfg.guild_id])

    @genius_or_submod_and_up()
    @tags.command(name="add")
    @app_commands.describe(name="Name of the tag")
    @app_commands.describe(image="Image to attach to the tag")
    @transform_context
    async def add(self, ctx: BlooContext, name: str, image: ImageAttachment = None) -> None:
        if not name.isalnum():
            raise commands.BadArgument("Tag name must be alphanumeric.")

        if len(name.split()) > 1:
            raise commands.BadArgument(
                "Tag names can't be longer than 1 word.")

        if (guild_service.get_tag(name.lower())) is not None:
            raise commands.BadArgument("Tag with that name already exists.")

        content_type = None
        if image is not None:
            content_type = image.content_type
            if image.size > 8_000_000:
                raise commands.BadArgument("That image is too big!")

            image = await image.read()

        modal = TagModal(bot=self.bot, tag_name=name, author=ctx.author)
        await ctx.interaction.response.send_modal(modal)
        await modal.wait()

        tag = modal.tag
        if tag is None:
            return

        # did the user want to attach an image to this tag?
        if image is not None:
            tag.image.put(image, content_type=content_type)

        # store tag in database
        guild_service.add_tag(tag)

        _file = tag.image.read()
        if _file is not None:
            _file = discord.File(BytesIO(
                _file), filename="image.gif" if tag.image.content_type == "image/gif" else "image.png")

        await ctx.send_followup(f"Added new tag!", file=_file or discord.utils.MISSING, embed=prepare_tag_embed(tag) or discord.utils.MISSING, view=prepare_tag_view(tag) or discord.utils.MISSING, delete_after=5)

    @genius_or_submod_and_up()
    @tags.command(description="Edit an existing tag")
    @app_commands.describe(name="Name of the tag")
    @app_commands.autocomplete(name=tags_autocomplete)
    @app_commands.describe(image="Image to attach to the tag")
    @transform_context
    async def edit(self, ctx: BlooContext, name: str, image: ImageAttachment = None) -> None:
        if len(name.split()) > 1:
            raise commands.BadArgument(
                "Tag names can't be longer than 1 word.")

        name = name.lower()
        tag = guild_service.get_tag(name)

        if tag is None:
            raise commands.BadArgument("That tag does not exist.")

        content_type = None
        if image is not None:
            # ensure the attached file is an image
            content_type = image.content_type
            if image.size > 8_000_000:
                raise commands.BadArgument("That image is too big!")

            image = await image.read()
            # save image bytes
            if tag.image is not None:
                tag.image.replace(image, content_type=content_type)
            else:
                tag.image.put(image, content_type=content_type)
        else:
            tag.image.delete()

        modal = EditTagModal(tag=tag, author=ctx.author)
        await ctx.interaction.response.send_modal(modal)
        await modal.wait()

        if not modal.edited:
            await ctx.send_warning("Tag edit was cancelled.", followup=True, ephemeral=True)
            return

        tag = modal.tag

        # store tag in database
        guild_service.edit_tag(tag)

        _file = tag.image.read()
        if _file is not None:
            _file = discord.File(BytesIO(
                _file), filename="image.gif" if tag.image.content_type == "image/gif" else "image.png")

        await ctx.send_followup(f"Edited tag!", file=_file or discord.utils.MISSING, embed=prepare_tag_embed(tag), view=prepare_tag_view(tag) or discord.utils.MISSING, delete_after=5)

    @genius_or_submod_and_up()
    @tags.command(description="Delete a tag")
    @app_commands.describe(name="Name of the tag")
    @app_commands.autocomplete(name=tags_autocomplete)
    @transform_context
    async def delete(self, ctx: BlooContext, name: str):
        name = name.lower()

        tag = guild_service.get_tag(name)
        if tag is None:
            raise commands.BadArgument("That tag does not exist.")

        if tag.image is not None:
            tag.image.delete()

        guild_service.remove_tag(name)
        await ctx.send_warning(f"Deleted tag `{tag.name}`.", delete_after=5)


async def setup(bot):
    await bot.add_cog(Tags(bot))
