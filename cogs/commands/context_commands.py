import functools
import random
from datetime import datetime
from io import BytesIO

import discord
from cogs.commands.info.tags import prepare_tag_embed, prepare_tag_view
from cogs.commands.info.userinfo import handle_userinfo
from data.services import guild_service
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping
from utils import GIRContext, cfg
from utils.framework import MessageTextBucket, gatekeeper
from utils.framework.checks import mod_and_up
from utils.framework.transformers import ModsAndAboveMember
from utils.views import PFPButton, PFPView
from utils.views.menus.report import manual_report
from utils.views.menus.report_action import WarnView

# support_tags = [tag.name for tag in await guild_service.get_guild(
# ).tags if "support" in tag.name]

tag_cooldown = CooldownMapping.from_cooldown(
    1, 5, MessageTextBucket.custom)


async def whisper(ctx: GIRContext):
    if not gatekeeper.has(ctx.guild, ctx.author, 5) and ctx.channel.id != (await guild_service.get_guild()).channel_botspam:
        ctx.whisper = True
    else:
        ctx.whisper = False

async def handle_support_tag(ctx: GIRContext, member: discord.Member) -> None:
    support_tags = [tag.name for tag in await guild_service.get_guild(
        ).tags if "support" in tag.name]

    if not support_tags:
        raise commands.BadArgument("No support tags found.")

    random_tag = random.choice(support_tags)
    tag = guild_service.get_tag(random_tag)

    if tag is None:
        raise commands.BadArgument("That tag does not exist.")

    # run cooldown so tag can't be spammed
    bucket = tag_cooldown.get_bucket(tag.name)
    current = datetime.now().timestamp()
    # ratelimit only if the invoker is not a moderator
    if bucket.update_rate_limit(current) and not (gatekeeper.has(ctx.guild, ctx.author, 5) or ctx.guild.get_role((await guild_service.get_guild()).role_sub_mod) in ctx.author.roles):
        raise commands.BadArgument("That tag is on cooldown.")

    # if the Tag has an image, add it to the embed
    file = tag.image.read()
    if file is not None:
        file = discord.File(BytesIO(
            file), filename="image.gif" if tag.image.content_type == "image/gif" else "image.png")

    title = f"Hey {member.mention}, have a look at this!"
    await ctx.respond_or_edit(content=title, embed=prepare_tag_embed(tag), file=file or discord.utils.MISSING, view=prepare_tag_view(tag))


async def handle_avatar(ctx, member: discord.Member):
    embed = discord.Embed(title=f"{member}'s avatar")
    animated = ["gif", "png", "jpeg", "webp"]
    not_animated = ["png", "jpeg", "webp"]

    avatar = member.avatar or member.default_avatar

    def fmt(format_):
        return f"[{format_}]({avatar.replace(format=format_, size=4096)})"

    if member.display_avatar.is_animated():
        embed.description = f"View As\n{'  '.join([fmt(format_) for format_ in animated])}"
    else:
        embed.description = f"View As\n{'  '.join([fmt(format_) for format_ in not_animated])}"

    embed.set_image(url=avatar.replace(size=4096))
    embed.color = discord.Color.random()

    view = PFPView(ctx)
    if member.guild_avatar is not None:
        view.add_item(PFPButton(ctx, member))

    view.message = await ctx.respond(embed=embed, ephemeral=ctx.whisper, view=view)


def setup_context_commands(bot: commands.Bot):
    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Support tag")
    async def support_tag_rc(interaction: discord.Interaction, user: discord.Member) -> None:
        ctx = GIRContext(interaction)
        await handle_support_tag(ctx, user)

    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Support tag")
    async def support_tag_msg(interaction: discord.Interaction, message: discord.Message) -> None:
        ctx = GIRContext(interaction)
        await handle_support_tag(ctx, message.author)

    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="View avatar")
    async def avatar_rc(interaction: discord.Interaction, member: discord.Member):
        ctx = GIRContext(interaction)
        await whisper(ctx)
        await handle_avatar(ctx, member)

    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="View avatar")
    async def avatar_msg(interaction: discord.Interaction, message: discord.Message):
        ctx = GIRContext(interaction)
        await whisper(ctx)
        await handle_avatar(ctx, message.author)

    @mod_and_up()
    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Warn 50 points")
    async def warn_rc(interaction: discord.Interaction, member: discord.Member) -> None:
        member = await ModsAndAboveMember.transform(interaction, member)
        ctx = GIRContext(interaction)
        ctx.whisper = True
        view = WarnView(ctx, member)
        await ctx.respond(embed=discord.Embed(description=f"Choose a warn reason for {member.mention}.", color=discord.Color.blurple()), view=view, ephemeral=True)

    @mod_and_up()
    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Warn 50 points")
    async def warn_msg(interaction: discord.Interaction, message: discord.Message) -> None:
        member = await ModsAndAboveMember.transform(interaction, message.author)
        ctx = GIRContext(interaction)
        ctx.whisper = True
        view = WarnView(ctx, message.author)
        await ctx.respond(embed=discord.Embed(description=f"Choose a warn reason for {message.author.mention}.", color=discord.Color.blurple()), view=view, ephemeral=True)

    @mod_and_up()
    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Generate report")
    async def generate_report_rc(interaction: discord.Interaction, member: discord.Member) -> None:
        ctx = GIRContext(interaction)
        ctx.whisper = True
        member = await ModsAndAboveMember.transform(interaction, member)
        await manual_report(ctx.author, member)
        await ctx.send_success("Generated report!")

    @mod_and_up()
    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Generate report")
    async def generate_report_msg(interaction: discord.Interaction, message: discord.Message) -> None:
        ctx = GIRContext(interaction)
        ctx.whisper = True
        member = await ModsAndAboveMember.transform(interaction, message.author)
        await manual_report(ctx.author, message)
        await ctx.send_success("Generated report!")

    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Userinfo")
    async def userinfo_rc(interaction: discord.Interaction, user: discord.Member) -> None:
        ctx = GIRContext(interaction)
        await whisper(ctx)
        await handle_userinfo(ctx, user)

    @bot.tree.context_menu(guild=discord.Object(id=cfg.guild_id), name="Userinfo")
    async def userinfo_msg(interaction: discord.Interaction, message: discord.Message) -> None:
        ctx = GIRContext(interaction)
        await whisper(ctx)
        await handle_userinfo(ctx, message.author)