from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping

from core import get_session
from core.service import TagService
from core.ui import format_taglist_page
from utils import GIRContext, cfg, transform_context
from utils.framework import (MessageTextBucket, gatekeeper,
                             whisper)
from utils.views import Menu, tags_autocomplete


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
    async def tag(self, ctx: GIRContext, name: str, user_to_mention: discord.Member = None):
        name = name.lower()
        async with get_session(self.bot.engine) as session:
            tag_service = TagService(session)
            result = await tag_service.get_tag(name)

        if result is None:
            raise commands.BadArgument("That tag does not exist.")

        tag = result.tag
        buttons = result.buttons

        # run cooldown so tag can't be spammed
        bucket = self.tag_cooldown.get_bucket(tag.phrase)
        current = datetime.now().timestamp()
        # ratelimit only if the invoker is not a moderator
        if bucket.update_rate_limit(current) and not (
                gatekeeper.has(ctx.guild, ctx.author, 5) or ctx.guild.get_role(cfg.roles.sub_mod) in ctx.author.roles):
            raise commands.BadArgument("That tag is on cooldown.")

        if user_to_mention is not None:
            title = f"Hey {user_to_mention.mention}, have a look at this!"
        else:
            title = None

        embed = TagService.prepare_tag_embed(tag)
        view = TagService.prepare_tag_button_view(buttons)

        await ctx.respond(content=title, embed=embed, view=view)

    @commands.guild_only()
    @commands.command(name="tag", aliases=["t"])
    async def _tag(self, ctx: commands.Context, name: str):
        name = name.lower()

        async with get_session(self.bot.engine) as session:
            tag_service = TagService(session)
            tag = await tag_service.get_tag(name)

        if tag is None:
            raise commands.BadArgument("That tag does not exist.")

        embed = tag_service.prepare_tag_embed(tag.tag)
        view = tag_service.prepare_tag_button_view(tag.buttons)

        if ctx.message.reference is not None:
            title = f"Hey {ctx.message.reference.resolved.author.mention}, have a look at this!"
            await ctx.send(content=title, embed=embed, view=view)
        else:
            await ctx.message.reply(embed=embed, view=view, mention_author=False)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="List all tags")
    @transform_context
    @whisper
    async def taglist(self, ctx: GIRContext):
        async with get_session(self.bot.engine) as session:
            tag_service = TagService(session)
            _tags = await tag_service.get_all_tags()

        if len(_tags) == 0:
            raise commands.BadArgument("There are no tags defined.")

        menu = Menu(ctx=ctx, entries=_tags, per_page=10, whisper=ctx.whisper, page_formatter=format_taglist_page)
        await menu.start()

    tags = app_commands.Group(name="tags", description="Interact with tags", guild_ids=[cfg.guild_id])

    # @genius_or_submod_and_up()
    # @tags.command(description="Create a tag")
    # @app_commands.describe(name="Name of the tag")
    # @app_commands.describe(image="Image to attach to the tag")
    # @transform_context
    # async def add(self, ctx: GIRContext, name: str, image: ImageAttachment = None) -> None:
    #     if not name.isalnum():
    #         raise commands.BadArgument("Tag name must be alphanumeric.")
    #
    #     if len(name.split()) > 1:
    #         raise commands.BadArgument(
    #             "Tag names can't be longer than 1 word.")
    #
    #     if (guild_service.get_tag(name.lower())) is not None:
    #         raise commands.BadArgument("Tag with that name already exists.")
    #
    #     modal = TagModal(bot=self.bot, tag_name=name, author=ctx.author)
    #     await ctx.interaction.response.send_modal(modal)
    #     await modal.wait()
    #
    #     tag = modal.tag
    #     if tag is None:
    #         return
    #
    #     # did the user want to attach an image to this tag?
    #     if image is not None:
    #         tag.image.put(image, content_type=content_type)
    #
    #     # store tag in database
    #     guild_service.add_tag(tag)
    #
    #     _file = tag.image.read()
    #     if _file is not None:
    #         _file = discord.File(BytesIO(
    #             _file), filename="image.gif" if tag.image.content_type == "image/gif" else "image.png")
    #
    #     await ctx.send_followup(f"Added new tag!", file=_file or discord.utils.MISSING,
    #                             embed=prepare_tag_embed(tag) or discord.utils.MISSING,
    #                             view=prepare_tag_view(tag) or discord.utils.MISSING, delete_after=5)
    #
    # @genius_or_submod_and_up()
    # @tags.command(description="Edit an existing tag")
    # @app_commands.describe(name="Name of the tag")
    # @app_commands.autocomplete(name=tags_autocomplete)
    # @app_commands.describe(image="Image to attach to the tag")
    # @transform_context
    # async def edit(self, ctx: GIRContext, name: str, image: ImageAttachment = None) -> None:
    #     if len(name.split()) > 1:
    #         raise commands.BadArgument(
    #             "Tag names can't be longer than 1 word.")
    #
    #     name = name.lower()
    #     tag = guild_service.get_tag(name)
    #
    #     if tag is None:
    #         raise commands.BadArgument("That tag does not exist.")
    #
    #     content_type = None
    #     if image is not None:
    #         # ensure the attached file is an image
    #         content_type = image.content_type
    #         if image.size > 8_000_000:
    #             raise commands.BadArgument("That image is too big!")
    #
    #         image = await image.read()
    #         # save image bytes
    #         if tag.image is not None:
    #             tag.image.replace(image, content_type=content_type)
    #         else:
    #             tag.image.put(image, content_type=content_type)
    #     else:
    #         tag.image.delete()
    #
    #     modal = EditTagModal(tag=tag, author=ctx.author)
    #     await ctx.interaction.response.send_modal(modal)
    #     await modal.wait()
    #
    #     if not modal.edited:
    #         await ctx.send_warning("Tag edit was cancelled.", followup=True, ephemeral=True)
    #         return
    #
    #     tag = modal.tag
    #
    #     # store tag in database
    #     guild_service.edit_tag(tag)
    #
    #     _file = tag.image.read()
    #     if _file is not None:
    #         _file = discord.File(BytesIO(
    #             _file), filename="image.gif" if tag.image.content_type == "image/gif" else "image.png")
    #
    #     await ctx.send_followup(f"Edited tag!", file=_file or discord.utils.MISSING, embed=prepare_tag_embed(tag),
    #                             view=prepare_tag_view(tag) or discord.utils.MISSING, delete_after=5)
    #
    # @genius_or_submod_and_up()
    # @tags.command(description="Delete a tag")
    # @app_commands.describe(name="Name of the tag")
    # @app_commands.autocomplete(name=tags_autocomplete)
    # @transform_context
    # async def delete(self, ctx: GIRContext, name: str):
    #     name = name.lower()
    #
    #     tag = guild_service.get_tag(name)
    #     if tag is None:
    #         raise commands.BadArgument("That tag does not exist.")
    #
    #     if tag.image is not None:
    #         tag.image.delete()
    #
    #     guild_service.remove_tag(name)
    #     await ctx.send_warning(f"Deleted tag `{tag.name}`.", delete_after=5)


async def setup(bot):
    await bot.add_cog(Tags(bot))
