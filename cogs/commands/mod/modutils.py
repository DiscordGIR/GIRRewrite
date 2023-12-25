import datetime
import typing

import discord
import pytz
from data.model import Case
from data.services import guild_service, user_service
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt
from utils import GIRContext, cfg, transform_context
from utils.framework import (ModsAndAboveMember, admin_and_up, always_whisper,
                             guild_owner_and_up, mod_and_up)
from utils.framework.transformers import ImageAttachment, ModsAndAboveMemberOrUser
from utils.views import (MONTH_MAPPING, command_list_autocomplete,
                         date_autocompleter)


class ModUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get information about a user (join/creation date, xp, etc.)")
    @app_commands.describe(member="The user to get information about")
    @transform_context
    async def rundown(self, ctx: GIRContext, member: discord.Member):
        await ctx.respond_or_edit(embed=await self.prepare_rundown_embed(ctx, member))

    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Transfer all data in the database between users")
    @app_commands.describe(old_member="The user to transfer data from")
    @app_commands.describe(new_member="The user to transfer data to")
    @transform_context
    async def transferprofile(self, ctx: GIRContext, old_member: ModsAndAboveMemberOrUser, new_member: ModsAndAboveMemberOrUser):
        if isinstance(old_member, int):
            try:
                old_member = await self.bot.fetch_user(old_member)
            except discord.NotFound:
                raise commands.BadArgument(
                    f"Couldn't find user with ID {old_member}")

        if isinstance(new_member, int):
            try:
                new_member = await self.bot.fetch_user(new_member)
            except discord.NotFound:
                raise commands.BadArgument(
                    f"Couldn't find user with ID {new_member}")

        u, case_count = user_service.transfer_profile(
            old_member.id, new_member.id)

        embed = discord.Embed(title="Transferred profile")
        embed.description = f"We transferred {old_member.mention}'s profile to {new_member.mention}"
        embed.color = discord.Color.blurple()
        embed.add_field(name="Level", value=u.level)
        embed.add_field(name="XP", value=u.xp)
        embed.add_field(name="Warnpoints", value=f"{u.warn_points} points")
        embed.add_field(
            name="Cases", value=f"We transferred {case_count} cases")

        await ctx.respond_or_edit(embed=embed, delete_after=10)

        try:
            await new_member.send(f"{ctx.author} has transferred your profile from {old_member}", embed=embed)
        except Exception:
            pass

    @guild_owner_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Sets user's XP and Level to 0, freezes XP, sets warn points to 599")
    @app_commands.describe(member="The user to reset")
    @transform_context
    async def clem(self, ctx: GIRContext, member: discord.Member):
        if member.id == ctx.author.id:
            await ctx.send_error("You can't call that on yourself.")
            raise commands.BadArgument("You can't call that on yourself.")
        if member.id == self.bot.user.id:
            await ctx.send_error("You can't call that on me :(")
            raise commands.BadArgument("You can't call that on me :(")

        results = user_service.get_user(member.id)
        results.is_clem = True
        results.is_xp_frozen = True
        results.warn_points = 599
        results.save()

        case = Case(
            _id=guild_service.get_guild().case_id,
            _type="CLEM",
            mod_id=ctx.author.id,
            mod_tag=str(ctx.author),
            punishment=str(-1),
            reason="No reason."
        )

        # incrememnt DB's max case ID for next case
        guild_service.inc_caseid()
        # add case to db
        user_service.add_case(member.id, case)

        await ctx.send_success(f"{member.mention} was put on clem.")

    @guild_owner_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Unclems user, sets warn points to 0 & unfreezes XP")
    @app_commands.describe(member="The user to unclem")
    @app_commands.describe(case_id="Case ID of the clem to lift")
    @app_commands.describe(reason="Reason for lifting the clem")
    @transform_context
    async def unclem(self, ctx: GIRContext, member: discord.Member, case_id: str, reason: str):
        results = user_service.get_user(member.id)
        if results.is_clem is False:
            await ctx.send_error(f"{member.mention} is not on clem.")
            raise commands.BadArgument(f"{member.mention} is not on clem.")

        results.is_clem = False
        results.is_xp_frozen = False
        results.warn_points = 0
        results.save()

        cases = user_service.get_cases(member.id)
        case = cases.cases.filter(_id=case_id).first()

        if case is None:
            raise commands.BadArgument(
                message=f"{member} has no case with ID {case_id}")
        elif case._type != "WARN":
            raise commands.BadArgument(
                message=f"{member}'s case with ID {case_id} is not a clem case.")
        elif case.lifted:
            raise commands.BadArgument(
                message=f"Case with ID {case_id} already lifted.")

        # passed sanity checks, so update the case in DB
        case.lifted = True
        case.lifted_reason = reason
        case.lifted_by_tag = str(ctx.author)
        case.lifted_by_id = ctx.author.id
        case.lifted_date = datetime.now()
        cases.save()

        # incrememnt DB's max case ID for next case
        guild_service.inc_caseid()
        # add case to db
        user_service.add_case(member.id, case)
        user_service.get_cases(member.id)
        embed = discord.Embed(title="Unclem", description="Generating new XP level based on current message count (this may take a while...)", color=discord.Color.green())
        embed.set_thumbnail(url=member.display_avatar)

        await ctx.respond_or_edit(embed)
        #TODO: Is there a better way to do this?
        xp_cog = self.bot.get_cog('cogs.monitors.utils.xp')
        for channel in await ctx.guild.fetch_channels():
            async for message in channel.history(limit=None, after=case.date, oldest=True):
                if message.author == member:
                    # Could just steal the code from the function but this is ~~lazier~~ easier
                    xp_cog.on_message(xp_cog, message)

        await ctx.send_success(f"{member.mention} was unclemmed.")

    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Freeze a user's XP")
    @app_commands.describe(member="The user to freeze")
    @transform_context
    async def freezexp(self, ctx: GIRContext, member: discord.Member):
        results = user_service.get_user(member.id)
        results.is_xp_frozen = not results.is_xp_frozen
        results.save()

        await ctx.send_success(f"{member.mention}'s xp was {'frozen' if results.is_xp_frozen else 'unfrozen'}.")

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Ban a user from birthdays")
    @app_commands.describe(member="The member to ban")
    @transform_context
    async def birthdayexclude(self, ctx: GIRContext, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send_error("You can't call that on me :(")
            raise commands.BadArgument("You can't call that on me :(")

        results = user_service.get_user(member.id)
        results.birthday_excluded = True
        results.birthday = None
        results.save()

        birthday_role = ctx.guild.get_role(
            guild_service.get_guild().role_birthday)
        if birthday_role is None:
            return

        if birthday_role in member.roles:
            await member.remove_roles(birthday_role)

        await ctx.send_success(f"{member.mention} was banned from birthdays.")

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Remove a user's birthday")
    @app_commands.describe(member="The member to remove the birthday from")
    @transform_context
    async def removebirthday(self, ctx: GIRContext, member: discord.Member):
        if member.id == self.bot.user.id:
            await ctx.send_error("You can't call that on me :(")
            raise commands.BadArgument("You can't call that on me :(")

        results = user_service.get_user(member.id)
        results.birthday = None
        results.save()

        try:
            ctx.tasks.cancel_unbirthday(member.id)
        except Exception:
            pass

        birthday_role = ctx.guild.get_role(
            guild_service.get_guild().role_birthday)
        if birthday_role is None:
            return

        if birthday_role in member.roles:
            await member.remove_roles(birthday_role)

        await ctx.send_success(f"{member.mention}'s birthday was removed.")

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Override a user's birthday")
    @app_commands.describe(member="The member to override the birthday of")
    @app_commands.describe(month="The month of the birthday")
    @app_commands.choices(month=[app_commands.Choice(name=month, value=month) for month in list(MONTH_MAPPING.keys())])
    @app_commands.describe(date="The date of the birthday")
    @app_commands.autocomplete(date=date_autocompleter)
    @transform_context
    async def setbirthday(self, ctx: GIRContext, member: discord.Member, month: str, date: int):
        month = MONTH_MAPPING.get(month)
        if month is None:
            raise commands.BadArgument("You gave an invalid date")

        month = month["value"]

        if member.id == self.bot.user.id:
            await ctx.send_error("You can't call that on me :(")
            raise commands.BadArgument("You can't call that on me :(")

        try:
            datetime.datetime(year=2020, month=month, day=date, hour=12)
        except ValueError:
            raise commands.BadArgument("You gave an invalid date.")

        results = user_service.get_user(member.id)
        results.birthday = [month, date]
        results.save()

        await ctx.send_success(f"{member.mention}'s birthday was set.")

        if results.birthday_excluded:
            return

        eastern = pytz.timezone('US/Eastern')
        today = datetime.datetime.today().astimezone(eastern)
        if today.month == month and today.day == date:
            birthday_role = ctx.guild.get_role(
                guild_service.get_guild().role_birthday)
            if birthday_role is None:
                return
            if birthday_role in member.roles:
                return
            now = datetime.datetime.now(eastern)
            h = now.hour / 24
            m = now.minute / 60 / 24

            try:
                time = now + datetime.timedelta(days=1-h-m)
                ctx.tasks.schedule_remove_bday(member.id, time)
            except Exception:
                return

            await member.add_roles(birthday_role)
            await member.send(f"According to my calculations, today is your birthday! We've hiven you the {birthday_role} role for 24 hours.")

    # TODO: this needs fixing
    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Toggle banning a user from using a command")
    @app_commands.describe(member="The member to ban")
    @app_commands.describe(command_name="The command to ban")
    @app_commands.autocomplete(command_name=command_list_autocomplete)
    @transform_context
    async def command_ban(self, ctx: GIRContext, member: ModsAndAboveMember, command_name: str):
        final_command = ""
        command: typing.Union[app_commands.Command, app_commands.Group] = self.bot.tree.get_command(command_name.split()[0].lower(), guild=ctx.guild)
        if not command_name:
                raise commands.BadArgument("That command doesn't exist.")

        final_command += command.name

        if isinstance(command, app_commands.Group):
            sub_command = command.get_command(command_name.split()[1].lower())
            if not sub_command:
                raise commands.BadArgument("That command doesn't exist.")

            final_command += f" {sub_command.name}"
        print(final_command)
        db_user = user_service.get_user(member.id)
        if final_command in db_user.command_bans:
            db_user.command_bans[final_command] = not db_user.command_bans[final_command]
        else:
            db_user.command_bans[final_command] = True

        db_user.save()

        await ctx.send_success(f"{member.mention} was {'banned' if db_user.command_bans[final_command] else 'unbanned'} from using `/{final_command}`.")

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Sayyyy")
    @app_commands.describe(message="The message to say")
    @app_commands.describe(image="Image to attach")
    @app_commands.describe(channel="The channel to say it in")
    @transform_context
    @always_whisper
    async def say(self, ctx: GIRContext, message: str, image: ImageAttachment = None, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        if image is not None:
            if image.size > 8_000_000:
                raise commands.BadArgument("Image is too big!")

            await channel.send(message, file=await image.to_file())
        else:
            await channel.send(message)
        await ctx.send_success("Done!")

        logging_channel = ctx.guild.get_channel(
            guild_service.get_guild().channel_private)

        embed = discord.Embed(color=discord.Color.gold(), title="Someone abused me :(",
                              description=f"In {ctx.channel.mention} {ctx.author.mention} said:\n\n{message}")
        await logging_channel.send(embed=embed)

    async def prepare_rundown_embed(self, ctx: GIRContext, user):
        user_info = user_service.get_user(user.id)
        rd = user_service.rundown(user.id)
        rd_text = ""
        for r in rd:
            if r._type == "WARN":
                r.punishment += " points"
            rd_text += f"**{r._type}** - {r.punishment} - {r.reason} - {format_dt(r.date, style='R')}\n"

        reversed_roles = user.roles
        reversed_roles.reverse()

        roles = ""
        for role in reversed_roles[0:4]:
            if role != user.guild.default_role:
                roles += role.mention + " "
        roles = roles.strip() + "..."

        embed = discord.Embed(title="Rundown")
        embed.color = user.color
        embed.set_thumbnail(url=user.display_avatar)

        embed.add_field(
            name="Member", value=f"{user} ({user.mention}, {user.id})")
        embed.add_field(name="Join date",
                        value=f"{format_dt(user.joined_at, style='F')} ({format_dt(user.joined_at, style='R')})")
        embed.add_field(name="Account creation date",
                        value=f"{format_dt(user.created_at, style='F')} ({format_dt(user.created_at, style='R')})")
        embed.add_field(name="Warn points",
                        value=user_info.warn_points, inline=True)

        if user_info.is_clem:
            embed.add_field(
                name="XP", value="*this user is clemmed*", inline=True)
        else:
            embed.add_field(
                name="XP", value=f"{user_info.xp} XP", inline=True)
            embed.add_field(
                name="Level", value=f"Level {user_info.level}", inline=True)

        embed.add_field(
            name="Roles", value=roles if roles else "None", inline=False)

        if len(rd) > 0:
            embed.add_field(name=f"{len(rd)} most recent cases",
                            value=rd_text, inline=False)
        else:
            embed.add_field(name="Recent cases",
                            value="This user has no cases.", inline=False)

        return embed

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="List all timed out users")
    @transform_context
    async def viewmuted(self, ctx: GIRContext):
        muted_members = [user for user in ctx.guild.members if user.is_timed_out()]

        if not muted_members:
            await ctx.send_warning("No one is muted.", delete_after=5)
            return

        new_line = "\n"
        muted_list = new_line.join([f"{user.mention} {user} — Unmuted {format_dt(user.timed_out_until, style='R')}" for user in sorted(muted_members[:8], key=lambda member: member.timed_out_until)])
        embed = discord.Embed(color=discord.Color.red(),
                              description=muted_list)
        embed.set_footer(text=f"{len(muted_members)} users muted")
        await ctx.respond_or_edit(content=None, embed=embed)


async def setup(bot):
    await bot.add_cog(ModUtils(bot))
