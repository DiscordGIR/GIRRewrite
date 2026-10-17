import asyncio
import discord

from typing import Union
from data.model.case import Case
from data.model.guild import Guild
from data.services.guild_service import guild_service
from data.services.user_service import user_service
from utils.context import GIRContext
from utils.mod.mod_logs import prepare_ban_log, prepare_kick_log

from utils.config import cfg


async def execute_kick(target_member, mod, reason, *, dm_text=None):
    """Only record successful kicks; keep notification before removal."""
    case = Case(
        _id=await guild_service.allocate_case_id(), _type="KICK",
        mod_id=mod.id, mod_tag=str(mod), reason=reason,
    )
    log = prepare_kick_log(mod, target_member, case)
    if dm_text is not None:
        await notify_user(target_member, dm_text, log)
    await target_member.kick(reason=reason)
    await user_service.add_case(target_member.id, case)
    return log


async def notify_user(target_member, text, log):
    """Notifies a specified user about something

    Parameters
    ----------
    user : discord.Member
        "User to notify"
    text : str
        "Text to send"
    log : discord.Embed
        "Embed to send"
    """
    try:
        await target_member.send(text, embed=log)
    except Exception:
        return False
    return True


async def notify_user_warn(ctx: GIRContext, target_member: discord.Member, mod: discord.Member, db_user, cur_points: int, log):
    """Notifies a specified user about a warn

    Parameters
    ----------
    ctx : GIRContext
        "Bot context"
    target_member : discord.Member
        "User to notify"
    mod : discord.Member
        "User that warned"
    db_user
        "User DB"
    db_guild
        "Guild DB"
    cur_points : int
        "Number of points the user currently has"
    log : discord.Embed
        "Embed to send"
    """
    log_kickban = None
    dmed = True

    if cur_points >= 600:
        # automatically ban user if more than 600 points

        if cfg.ban_appeal_url is None:
            dmed = await notify_user(target_member, f"You were banned from {ctx.guild.name} for reaching 600 or more points.", log)
        else:
            dmed = await notify_user(target_member, f"You were banned from {ctx.guild.name} for reaching 600 or more points.\n\nIf you would like to appeal your ban, please fill out this form: <{cfg.ban_appeal_url}>", log)

        bot = ctx.client if isinstance(ctx, discord.Interaction) else ctx.bot
        log_kickban = await execute_ban(bot, ctx.guild, target_member, mod,
                                        "600 or more warn points reached.")

    elif cur_points >= 400 and not db_user.was_warn_kicked and isinstance(target_member, discord.Member):
        # kick user if >= 400 points and wasn't previously kicked

        dmed = await notify_user(target_member, f"You were kicked from {ctx.guild.name} for reaching 400 or more points. Please note that you will be banned at 600 points.", log)
        log_kickban = await execute_kick(target_member, mod, "400 or more warn points reached.")
        await user_service.set_warn_kicked(target_member.id)
    else:
        if isinstance(target_member, discord.Member):
            dmed = await notify_user(target_member, f"You were warned in {ctx.guild.name}. Please note that you will be kicked at 400 points and banned at 600 points.", log)

    if log_kickban:
        await submit_public_log(ctx, target_member, log_kickban)

    return dmed


async def response_log(ctx, log):
    if isinstance(ctx, GIRContext):
        if ctx.interaction.response.is_done():
            res = await ctx.interaction.followup.send(embed=log)
            await res.delete(delay=10)
        else:
            await ctx.interaction.response.send_message(embed=log)
            ctx.bot.loop.create_task(delay_delete(ctx.interaction))
    elif isinstance(ctx, discord.Interaction):
        if ctx.response.is_done():
            res = await ctx.followup.send(embed=log)
            await res.delete(delay=10)
        else:
            await ctx.response.send_message(embed=log)
            ctx.client.loop.create_task(delay_delete(ctx))

    else:
        await ctx.send(embed=log, delete_after=10)


async def submit_public_log(ctx: GIRContext, user: Union[discord.Member, discord.User], log, dmed: bool = None):
    """Submits a public log

    Parameters
    ----------
    ctx : GIRContext
        "Bot context"
    user : discord.Member
        "User to notify"
    db_user
        "User DB"
    db_guild
        "Guild DB"
    cur_points : int
        "Number of points the user currently has"
    log : discord.Embed
        "Embed to send"
    """
    public_chan = ctx.guild.get_channel(
        cfg.channels.public_logs)
    if public_chan:
        log.remove_author()
        log.set_thumbnail(url=user.display_avatar)
        if dmed is not None:
            await public_chan.send(user.mention if not dmed else "", embed=log)
        else:
            await public_chan.send(embed=log)


async def execute_ban(bot, guild, target_member, mod, reason, *, dm_text=None, anonymous=False):
    """Record bans and update the cache only after Discord accepts the action."""
    case = Case(
        _id=await guild_service.allocate_case_id(), _type="BAN",
        mod_id=mod.id, mod_tag=str(mod), punishment="PERMANENT", reason=reason,
    )
    log = prepare_ban_log(mod, target_member, case)
    if anonymous:
        log.set_field_at(1, name="Mod", value=f"{guild.name} Staff")
    if dm_text is not None:
        await notify_user(target_member, dm_text, log)
    await guild.ban(discord.Object(id=target_member.id), reason=reason)
    bot.ban_cache.ban(target_member.id)
    await user_service.add_case(target_member.id, case)
    return log

async def delay_delete(ctx: discord.Interaction):
    await asyncio.sleep(10)
    await ctx.delete_original_response()
