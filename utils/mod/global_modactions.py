from datetime import timedelta
from typing import Union

import discord
import humanize
from data.model import Case
from data.services import guild_service, user_service
from discord.utils import escape_markdown
from utils import cfg

from .mod_logs import prepare_mute_log, prepare_unmute_log, prepare_warn_log
from .modactions_helpers import (add_ban_case, notify_user, notify_user_warn, response_log,
                                 submit_public_log)


async def mute(ctx, target_member: discord.Member, mod: discord.Member, dur_seconds=None, reason="No reason."):
    """Mutes a member

    Parameters
    ----------
    ctx : BlooContext
        "Bot context"
    member : discord.Member
        "Member to mute"
    dur_seconds : int
        "Mute duration in settings"
    reason : str
        "Reason for mute"

    """

    now = discord.utils.utcnow()

    if dur_seconds is not None:
        time = now + timedelta(seconds=dur_seconds)
        if time > now + timedelta(days=14):
            time = now + timedelta(days=14)
    else:
        time = now + timedelta(days=14)

    db_guild = guild_service.get_guild()
    case = Case(
        _id=db_guild.case_id,
        _type="MUTE",
        date=now,
        mod_id=mod.id,
        mod_tag=str(mod),
        reason=reason,
    )

    case.until = time
    case.punishment = humanize.naturaldelta(
        time - now, minimum_unit="seconds")
    try:
        await target_member.timeout(time, reason=reason)
        if isinstance(ctx, discord.Interaction):
            ctx.client.tasks.schedule_untimeout(target_member.id, time)
        else:
            ctx.bot.tasks.schedule_untimeout(target_member.id, time)
    except Exception:
        return

    guild_service.inc_caseid()
    user_service.add_case(target_member.id, case)

    log = prepare_mute_log(mod, target_member, case)
    await response_log(ctx, log)

    log.remove_author()
    log.set_thumbnail(url=target_member.display_avatar)

    dmed = await notify_user(target_member, f"You have been muted in {ctx.guild.name}", log)
    await submit_public_log(ctx, db_guild, target_member, log, dmed)


async def unmute(ctx, target_member: discord.Member, mod: discord.Member, reason: str = "No reason.") -> None:
    """Unmutes a user (mod only)

    Example usage
    --------------
    /unmute member:<member> reason:<reason>

    Parameters
    ----------
    user : discord.Member
        "Member to unmute"
    reason : str, optional
        "Reason for unmute, by default 'No reason.'"

    """

    await target_member.edit(timed_out_until=None)
    db_guild = guild_service.get_guild()

    try:
        if isinstance(ctx, discord.Interaction):
            ctx.client.tasks.cancel_unmute(target_member.id)
        else:
            ctx.tasks.cancel_unmute(target_member.id)
    except Exception as e:
        pass

    case = Case(
        _id=db_guild.case_id,
        _type="UNMUTE",
        mod_id=mod.id,
        mod_tag=str(mod),
        reason=reason,
    )

    guild_service.inc_caseid()
    user_service.add_case(target_member.id, case)

    log = prepare_unmute_log(mod, target_member, case)
    await response_log(ctx, log)

    dmed = await notify_user(target_member, f"You have been unmuted in {ctx.guild.name}", log)
    await submit_public_log(ctx, db_guild, target_member, log, dmed)


async def ban(ctx, target_member: Union[discord.Member, discord.User], mod: discord.Member, reason="No reason."):
    db_guild = guild_service.get_guild()

    member_is_external = isinstance(target_member, discord.User)
    log = await add_ban_case(target_member, mod, reason, db_guild)

    if not member_is_external:
        if cfg.ban_appeal_url is None:
            await notify_user(target_member, f"You have been banned from {ctx.guild.name}", log)
        else:
            await notify_user(target_member, f"You have been banned from {ctx.guild.name}\n\nIf you would like to appeal your ban, please fill out this form: <{cfg.ban_appeal_url}>", log)

        await target_member.ban(reason=reason)
    else:
        # hackban for user not currently in guild
        await ctx.guild.ban(discord.Object(id=target_member.id))

    # TODO: fix
    # ctx.bot.ban_cache.ban(target_member.id)
    await response_log(ctx, log)
    await submit_public_log(ctx, db_guild, target_member, log)


async def warn(ctx, target_member: discord.Member, mod: discord.Member, points, reason):
    db_guild = guild_service.get_guild()

    reason = escape_markdown(reason)

    # prepare the case object for database
    case = Case(
        _id=db_guild.case_id,
        _type="WARN",
        mod_id=mod.id,
        mod_tag=str(mod.id),
        reason=reason,
        punishment=str(points)
    )

    # increment case ID in database for next available case ID
    guild_service.inc_caseid()
    # add new case to DB
    user_service.add_case(target_member.id, case)
    # add warnpoints to the user in DB
    user_service.inc_points(target_member.id, points)

    # fetch latest document about user from DB
    db_user = user_service.get_user(target_member.id)
    cur_points = db_user.warn_points

    # prepare log embed, send to #public-mod-logs, user, channel where invoked
    log = prepare_warn_log(mod, target_member, case)
    log.add_field(name="Current points", value=cur_points, inline=True)

    # also send response in channel where command was called
    dmed = await notify_user_warn(ctx, target_member, mod, db_user, db_guild, cur_points, log)
    await response_log(ctx, log)
    await submit_public_log(ctx, db_guild, target_member, log, dmed)

