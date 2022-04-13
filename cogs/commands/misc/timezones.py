import datetime
import discord
import flag
import pytz
from discord import app_commands
from discord.ext import commands
from data.services import user_service
from utils import GIRContext, cfg, transform_context
from utils.framework import whisper
from utils.views import timezone_autocomplete


class Timezones(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timezone_country = {}
        for countrycode in pytz.country_timezones:
            timezones = pytz.country_timezones[countrycode]
            for timezone in timezones:
                self.timezone_country[timezone] = countrycode

    timezone = app_commands.Group(
        name="timezone", description="Interact with timezones", guild_ids=[cfg.guild_id])

    @timezone.command(name="set", description="Set your timezone so that others can view it")
    @app_commands.describe(zone="The timezone to set")
    @app_commands.autocomplete(zone=timezone_autocomplete)
    @transform_context
    @whisper
    async def _set(self, ctx: GIRContext, zone: str):
        if zone not in pytz.common_timezones_set:
            raise commands.BadArgument("Timezone was not found!")

        db_user = user_service.get_user(ctx.author.id)
        db_user.timezone = zone
        db_user.save()

        await ctx.send_success(f"We set your timezone to `{zone}`! It can now be viewed with `/timezone view`.", ephemeral=ctx.whisper)

    @timezone.command(name="remove", description="Remove your timezone from the database")
    @transform_context
    @whisper
    async def remove(self, ctx: GIRContext):
        db_user = user_service.get_user(ctx.author.id)
        db_user.timezone = None
        db_user.save()

        await ctx.send_success(f"We have removed your timezone from the database.", ephemeral=ctx.whisper)

    @timezone.command(name="view", description="View the local time in someone else's timezone")
    @app_commands.describe(member="Member to view time of")
    @transform_context
    @whisper
    async def view(self, ctx: GIRContext, member: discord.Member):
        db_user = user_service.get_user(member.id)
        if db_user.timezone is None:
            raise commands.BadArgument(f"{member.mention} has not set a timezone!")

        country_code = self.timezone_country.get(db_user.timezone)
        flaggy = ""
        if country_code is not None:
            try:
                flaggy = " " + flag.flag(country_code)
            except ValueError:
                pass

        await ctx.send_success(description=f"{member.mention}'s timezone is `{db_user.timezone}` {flaggy}\nIt is currently `{datetime.datetime.now(pytz.timezone(db_user.timezone)).strftime('%I:%M %p %Z')}`", ephemeral=ctx.whisper)


async def setup(bot: commands.Bot):
    await bot.add_cog(Timezones(bot))
