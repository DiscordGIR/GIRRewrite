from datetime import datetime, timedelta, timezone

import discord
import humanize
from apscheduler.jobstores.base import ConflictingIdError
from data.model import Case
from data.services import guild_service, user_service
from discord import app_commands
from discord.ext import commands
from discord.utils import escape_markdown, escape_mentions
from utils import BlooContext, cfg, transform_context
from utils.framework import always_whisper, mod_and_up, ModsAndAboveMemberOrUser
from utils.framework.transformers import Duration, ModsAndAboveMember
from utils.mod import (add_ban_case, add_kick_case, notify_user,
                       prepare_editreason_log, prepare_liftwarn_log,
                       prepare_mute_log, prepare_removepoints_log,
                       prepare_unban_log, prepare_unmute_log,
                       submit_public_log)
from utils.mod.global_modactions import warn
# from utils.views import liftwarn_autocomplete


class ModActions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="warn a user")
    @app_commands.describe(user="User to warn")
    @app_commands.describe(points="Points to warn the user with")
    @app_commands.describe(reason="Reason for warning")
    @transform_context
    async def warn(self, ctx: BlooContext, user: ModsAndAboveMemberOrUser, points: app_commands.Range[int, 1, 600], reason: str):
        if points < 1:  # can't warn for negative/0 points
            raise commands.BadArgument(message="Points can't be lower than 1.")

        await warn(ctx, target_member=user, mod=ctx.author, points=points, reason=reason)

    # @mod_and_up()
    # @always_whisper()
    # @user_command(guild_ids=[cfg.guild_id], name="Warn 50 points")
    # async def warn_rc(self, ctx: BlooContext, member: discord.Member) -> None:
    #     member = await mods_and_above_external_resolver(ctx, member)
    #     view = WarnView(ctx, member)
    #     await ctx.respond(embed=discord.Embed(description=f"Choose a warn reason for {member.mention}.", color=discord.Color.blurple()), view=view, ephemeral=True)

    # @mod_and_up()
    # @always_whisper()
    # @message_command(guild_ids=[cfg.guild_id], name="Warn 50 points")
    # async def warn_msg(self, ctx: BlooContext, message: discord.Message) -> None:
    #     member = await mods_and_above_external_resolver(ctx, message.author)
    #     view = WarnView(ctx, message.author)
    #     await ctx.respond(embed=discord.Embed(description=f"Choose a warn reason for {member.mention}.", color=discord.Color.blurple()), view=view, ephemeral=True)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Kick a user")
    @app_commands.describe(member="User to kick")
    @app_commands.describe(reason="Reason for kicking")
    @transform_context
    async def kick(self, ctx: BlooContext, member: ModsAndAboveMember, reason: str) -> None:
        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        db_guild = guild_service.get_guild()

        log = add_kick_case(target_member=member, mod=ctx.author, reason=reason, db_guild=db_guild)
        await notify_user(member, f"You were kicked from {ctx.guild.name}", log)

        await member.kick(reason=reason)

        await ctx.respond_or_edit(embed=log, delete_after=10)
        await submit_public_log(ctx, db_guild, member, log)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Kick a user")
    @app_commands.describe(member="User to kick")
    @transform_context
    async def roblox(self, ctx: BlooContext, member: ModsAndAboveMember) -> None:
        reason = "This Discord server is for iOS jailbreaking, not Roblox. Please join https://discord.gg/jailbreak instead, thank you!"

        db_guild = guild_service.get_guild()

        log = add_kick_case(target_member=member, mod=ctx.author, reason=reason, db_guild=db_guild)
        await notify_user(member, f"You were kicked from {ctx.guild.name}", log)

        await member.kick(reason=reason)

        await ctx.respond_or_edit(embed=log, delete_after=10)
        await submit_public_log(ctx, db_guild, member, log)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Mute a user")
    @app_commands.describe(member="User to mute")
    @app_commands.describe(duration="Duration of the mute (i.e 10m, 1h, 1d...)")
    @app_commands.describe(reason="Reason for muting")
    @transform_context
    async def mute(self, ctx: BlooContext, member: ModsAndAboveMember, duration: Duration, reason: str = "No reason.") -> None:
        reason = escape_markdown(reason)
        reason = escape_mentions(reason)

        now = datetime.now(tz=timezone.utc)
        delta = duration

        if delta is None:
            raise commands.BadArgument("Please input a valid duration!")

        if member.is_timed_out():
            raise commands.BadArgument("This user is already muted.")

        time = now + timedelta(seconds=delta)
        if time > now + timedelta(days=14):
            raise commands.BadArgument("Mutes can't be longer than 14 days!")

        db_guild = guild_service.get_guild()
        case = Case(
            _id=db_guild.case_id,
            _type="MUTE",
            date=now,
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            reason=reason,
        )

        case.until = time
        case.punishment = humanize.naturaldelta(
            time - now, minimum_unit="seconds")

        try:
            await member.timeout(time, reason=reason)
            ctx.tasks.schedule_untimeout(member.id, time)
        except ConflictingIdError:
            raise commands.BadArgument(
                "The database thinks this user is already muted.")

        guild_service.inc_caseid()
        user_service.add_case(member.id, case)

        log = prepare_mute_log(ctx.author, member, case)
        await ctx.respond_or_edit(embed=log, delete_after=10)

        log.remove_author()
        log.set_thumbnail(url=member.display_avatar)

        dmed = await notify_user(member, f"You have been muted in {ctx.guild.name}", log)
        await submit_public_log(ctx, db_guild, member, log, dmed)

    # @mod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Unmute a user", permissions=slash_perms.mod_and_up())
    # async def unmute(self, ctx: BlooContext, member: Option(discord.Member, description="User to mute"), reason: Option(str, description="Reason for mute")) -> None:
    #     """Unmutes a user (mod only)

    #     Example usage
    #     --------------
    #     /unmute member:<member> reason:<reason>

    #     Parameters
    #     ----------
    #     user : discord.Member
    #         "Member to unmute"
    #     reason : str, optional
    #         "Reason for unmute, by default 'No reason.'"

    #     """

    #     member = await mods_and_above_member_resolver(ctx, member)

    #     db_guild = guild_service.get_guild()

    #     if not member.timed_out:
    #         raise commands.BadArgument("This user is not muted.")

    #     await member.remove_timeout()

    #     try:
    #         ctx.tasks.cancel_unmute(member.id)
    #     except Exception:
    #         pass

    #     case = Case(
    #         _id=db_guild.case_id,
    #         _type="UNMUTE",
    #         mod_id=ctx.author.id,
    #         mod_tag=str(ctx.author),
    #         reason=reason,
    #     )
    #     guild_service.inc_caseid()
    #     user_service.add_case(member.id, case)

    #     log = prepare_unmute_log(ctx.author, member, case)

    #     await ctx.respond(embed=log, delete_after=10)

    #     dmed = await notify_user(member, f"You have been unmuted in {ctx.guild.name}", log)
    #     await submit_public_log(ctx, db_guild, member, log, dmed)

    # @mod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Ban a user", permissions=slash_perms.mod_and_up())
    # async def ban(self, ctx: BlooContext, user: Option(discord.Member, description="User to ban"), reason: Option(str, description="Reason for ban")):
    #     """Bans a user (mod only)

    #     Example usage
    #     --------------
    #     /ban user:<user> reason:<reason>

    #     Parameters
    #     ----------
    #     user : discord.Member
    #         "The user to be banned, doesn't have to be part of the guild"
    #     reason : str, optional
    #         "Reason for ban, by default 'No reason.'"

    #     """

    #     user = await mods_and_above_external_resolver(ctx, user)

    #     reason = escape_markdown(reason)
    #     reason = escape_mentions(reason)
    #     db_guild = guild_service.get_guild()

    #     await ctx.defer(ephemeral=False)
    #     member_is_external = isinstance(user, discord.User)

    #     # if the ID given is of a user who isn't in the guild, try to fetch the profile
    #     if member_is_external:
    #         if self.bot.ban_cache.is_banned(user.id):
    #             raise commands.BadArgument("That user is already banned!")

    #     self.bot.ban_cache.ban(user.id)
    #     log = await add_ban_case(ctx, user, reason, db_guild)

    #     if not member_is_external:
    #         if cfg.ban_appeal_url is None:
    #             await notify_user(user, f"You have been banned from {ctx.guild.name}", log)
    #         else:
    #             await notify_user(user, f"You have been banned from {ctx.guild.name}\n\nIf you would like to appeal your ban, please fill out this form: <{cfg.ban_appeal_url}>", log)

    #         await user.ban(reason=reason)
    #     else:
    #         # hackban for user not currently in guild
    #         await ctx.guild.ban(discord.Object(id=user.id))

    #     await ctx.respond(embed=log, delete_after=10)
    #     await submit_public_log(ctx, db_guild, user, log)

    # @mod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Unban a user", permissions=slash_perms.mod_and_up())
    # async def unban(self, ctx: BlooContext, user: Option(discord.Member, description="User to unban"), reason: Option(str, description="Reason for unban")) -> None:
    #     """Unbans a user (must use ID) (mod only)

    #     Example usage
    #     --------------
    #     /unban user:<userid> reason:<reason>

    #     Parameters
    #     ----------
    #     user : discord.Member
    #         "ID of the user to unban"
    #     reason : str, optional
    #         "Reason for unban, by default 'No reason.'"

    #     """

    #     user = await user_resolver(ctx, user)
    #     if ctx.guild.get_member(user.id) is not None:
    #         raise commands.BadArgument(
    #             "You can't unban someone already in the server!")

    #     reason = escape_markdown(reason)
    #     reason = escape_mentions(reason)

    #     if not self.bot.ban_cache.is_banned(user.id):
    #         raise commands.BadArgument("That user isn't banned!")

    #     try:
    #         await ctx.guild.unban(discord.Object(id=user.id), reason=reason)
    #     except discord.NotFound:
    #         raise commands.BadArgument(f"{user} is not banned.")

    #     self.bot.ban_cache.unban(user.id)

    #     db_guild = guild_service.get_guild()
    #     case = Case(
    #         _id=db_guild.case_id,
    #         _type="UNBAN",
    #         mod_id=ctx.author.id,
    #         mod_tag=str(ctx.author),
    #         reason=reason,
    #     )
    #     guild_service.inc_caseid()
    #     user_service.add_case(user.id, case)

    #     log = prepare_unban_log(ctx.author, user, case)
    #     await ctx.respond(embed=log, delete_after=10)

    #     await submit_public_log(ctx, db_guild, user, log)

    # @mod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Purge channel messages", permissions=slash_perms.mod_and_up())
    # async def purge(self, ctx: BlooContext, limit: Option(int, description="Number of messages to remove", min_value=1, max_value=100)) -> None:
    #     """Purges messages from current channel (mod only)

    #     Example usage
    #     --------------
    #     /purge limit:<number of messages>

    #     Parameters
    #     ----------
    #     limit : int, optional
    #         "Number of messages to purge, must be > 0, by default 0 for error handling"

    #     """

    #     if limit <= 0:
    #         raise commands.BadArgument(
    #             "Number of messages to purge must be greater than 0")
    #     elif limit >= 100:
    #         limit = 100

    #     msgs = await ctx.channel.history(limit=limit).flatten()

    #     await ctx.channel.purge(limit=limit)
    #     await ctx.respond(f'Purged {len(msgs)} messages.', delete_after=10)

    # @mod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Lift a warn", permissions=slash_perms.mod_and_up())
    # async def liftwarn(self, ctx: BlooContext, user: Option(discord.Member, description="User to lift warn of"), case_id: Option(str, autocomplete=liftwarn_autocomplete), reason: Option(str)) -> None:
    #     """Marks a warn as lifted and remove points. (mod only)

    #     Example usage
    #     --------------
    #     /liftwarn user:<user> case_id:<case ID> reason:<reason>

    #     Parameters
    #     ----------
    #     user : discord.Member
    #         "User to remove warn from"
    #     case_id : int
    #         "The ID of the case for which we want to remove points"
    #     reason : str, optional
    #         "Reason for lifting warn, by default 'No reason.'"

    #     """

    #     user = await mods_and_above_external_resolver(ctx, user)

    #     # retrieve user's case with given ID
    #     cases = user_service.get_cases(user.id)
    #     case = cases.cases.filter(_id=case_id).first()

    #     reason = escape_markdown(reason)
    #     reason = escape_mentions(reason)

    #     # sanity checks
    #     if case is None:
    #         raise commands.BadArgument(
    #             message=f"{user} has no case with ID {case_id}")
    #     elif case._type != "WARN":
    #         raise commands.BadArgument(
    #             message=f"{user}'s case with ID {case_id} is not a warn case.")
    #     elif case.lifted:
    #         raise commands.BadArgument(
    #             message=f"Case with ID {case_id} already lifted.")

    #     u = user_service.get_user(id=user.id)
    #     if u.warn_points - int(case.punishment) < 0:
    #         raise commands.BadArgument(
    #             message=f"Can't lift Case #{case_id} because it would make {user.mention}'s points negative.")

    #     # passed sanity checks, so update the case in DB
    #     case.lifted = True
    #     case.lifted_reason = reason
    #     case.lifted_by_tag = str(ctx.author)
    #     case.lifted_by_id = ctx.author.id
    #     case.lifted_date = datetime.now()
    #     cases.save()

    #     # remove the warn points from the user in DB
    #     user_service.inc_points(user.id, -1 * int(case.punishment))
    #     dmed = True
    #     # prepare log embed, send to #public-mod-logs, user, channel where invoked
    #     log = prepare_liftwarn_log(ctx.author, user, case)
    #     dmed = await notify_user(user, f"Your warn has been lifted in {ctx.guild}.", log)

    #     await ctx.respond(embed=log, delete_after=10)
    #     await submit_public_log(ctx, guild_service.get_guild(), user, log, dmed)

    # @mod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Edit case reason", permissions=slash_perms.mod_and_up())
    # async def editreason(self, ctx: BlooContext, user: Option(discord.Member), case_id: Option(int, autocomplete=liftwarn_autocomplete), new_reason: Option(str)) -> None:
    #     """Edits a case's reason and the embed in #public-mod-logs. (mod only)

    #     Example usage
    #     --------------
    #     /editreason user:<user> case_id:<case ID> reason:<reason>

    #     Parameters
    #     ----------
    #     user : discord.Member
    #         "User to edit case of"
    #     case_id : int
    #         "The ID of the case for which we want to edit reason"
    #     new_reason : str
    #         "New reason"

    #     """

    #     user = await mods_and_above_external_resolver(ctx, user)

    #     # retrieve user's case with given ID
    #     cases = user_service.get_cases(user.id)
    #     case = cases.cases.filter(_id=case_id).first()

    #     new_reason = escape_markdown(new_reason)
    #     new_reason = escape_mentions(new_reason)

    #     # sanity checks
    #     if case is None:
    #         raise commands.BadArgument(
    #             message=f"{user} has no case with ID {case_id}")

    #     old_reason = case.reason
    #     case.reason = new_reason
    #     case.date = datetime.now()
    #     cases.save()

    #     dmed = True
    #     log = prepare_editreason_log(ctx.author, user, case, old_reason)

    #     dmed = await notify_user(user, f"Your case was updated in {ctx.guild.name}.", log)

    #     public_chan = ctx.guild.get_channel(
    #         guild_service.get_guild().channel_public)

    #     found = False
    #     async with ctx.typing():
    #         async for message in public_chan.history(limit=200):
    #             if message.author.id != ctx.me.id:
    #                 continue
    #             if len(message.embeds) == 0:
    #                 continue
    #             embed = message.embeds[0]

    #             if embed.footer.text == discord.Embed.Empty:
    #                 continue
    #             if len(embed.footer.text.split(" ")) < 2:
    #                 continue

    #             if f"#{case_id}" == embed.footer.text.split(" ")[1]:
    #                 for i, field in enumerate(embed.fields):
    #                     if field.name == "Reason":
    #                         embed.set_field_at(
    #                             i, name="Reason", value=new_reason)
    #                         await message.edit(embed=embed)
    #                         found = True
    #     if found:
    #         await ctx.respond(f"We updated the case and edited the embed in {public_chan.mention}.", embed=log, delete_after=10)
    #     else:
    #         await ctx.respond(f"We updated the case but weren't able to find a corresponding message in {public_chan.mention}!", embed=log, delete_after=10)
    #         log.remove_author()
    #         log.set_thumbnail(url=user.display_avatar)
    #         await public_chan.send(user.mention if not dmed else "", embed=log)

    # @mod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Edit case reason", permissions=slash_perms.mod_and_up())
    # async def removepoints(self, ctx: BlooContext, user: Option(discord.Member), points: Option(int), reason: Option(str)) -> None:
    #     """Removes warnpoints from a user. (mod only)

    #     Example usage
    #     --------------
    #     /removepoints user:<user> points:<points> reasons:<reason>

    #     Parameters
    #     ----------
    #     user : discord.Member
    #         "User to remove warn from"
    #     points : int
    #         "Amount of points to remove"
    #     reason : str, optional
    #         "Reason for lifting warn, by default 'No reason.'"

    #     """

    #     user = await mods_and_above_external_resolver(ctx, user)

    #     reason = escape_markdown(reason)
    #     reason = escape_mentions(reason)

    #     if points < 1:
    #         raise commands.BadArgument("Points can't be lower than 1.")

    #     u = user_service.get_user(id=user.id)
    #     if u.warn_points - points < 0:
    #         raise commands.BadArgument(
    #             message=f"Can't remove {points} points because it would make {user.mention}'s points negative.")

    #     # passed sanity checks, so update the case in DB
    #     # remove the warn points from the user in DB
    #     user_service.inc_points(user.id, -1 * points)

    #     db_guild = guild_service.get_guild()
    #     case = Case(
    #         _id=db_guild.case_id,
    #         _type="REMOVEPOINTS",
    #         mod_id=ctx.author.id,
    #         mod_tag=str(ctx.author),
    #         punishment=str(points),
    #         reason=reason,
    #     )

    #     # increment DB's max case ID for next case
    #     guild_service.inc_caseid()
    #     # add case to db
    #     user_service.add_case(user.id, case)

    #     # prepare log embed, send to #public-mod-logs, user, channel where invoked
    #     log = prepare_removepoints_log(ctx.author, user, case)
    #     dmed = await notify_user(user, f"Your points were removed in {ctx.guild.name}.", log)

    #     await ctx.respond(embed=log, delete_after=10)
    #     await submit_public_log(ctx, db_guild, user, log, dmed)


async def setup(bot):
    await bot.add_cog(ModActions(bot))
