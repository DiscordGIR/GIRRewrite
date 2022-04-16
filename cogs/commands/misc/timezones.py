import datetime
from typing import List
import discord
import flag
import pytz
from discord import app_commands
from discord.ext import commands
from data.services import user_service
from utils import GIRContext, cfg, transform_context
from utils.framework import whisper, always_whisper
from utils.views import timezone_autocomplete, Menu

def country_code_to_emoji(country_code: str):
    try:
        return " " + flag.flag(country_code)
    except ValueError:
        return ""

def format_tz_page(ctx, entries, current_page, all_pages):
    if ctx.country_code is not None:
        title = f"Timezones in {country_code_to_emoji(ctx.country_code.upper())}"
        body = "\n".join(entries)
    else:
        title = "All timezones"
        body = ""
        for entry in entries:
            country_code = Timezones.timezone_country.get(entry)
            if country_code is not None:
                body += f"{country_code_to_emoji(country_code)} {entry}\n"
            else:
                body += f"{entry}\n"

    embed = discord.Embed(
        title=title, color=discord.Color.blurple())

    embed.description = body
    embed.set_footer(text=f"Page {current_page}/{len(all_pages)}")
    return embed


async def timezone_country_autocomplete(_: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    countries = list(pytz.country_timezones.keys())
    countries.sort()
    return [app_commands.Choice(name=country, value=country) for country in countries if current.lower() in country.lower()][:25]


class Timezones(commands.Cog):
    timezone_country = {}
    for countrycode in pytz.country_timezones:
        timezones = pytz.country_timezones[countrycode]
        for timezone in timezones:
            timezone_country[timezone] = countrycode

    def __init__(self, bot):
        self.bot = bot

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

        footer = None
        if self.timezone_country.get(zone) is None:
            footer = "Tip: this timezone is not a city. Pick a major city near you to show what country you're in! See /timezone list for more."

        await ctx.send_success(f"We set your timezone to `{zone}`! It can now be viewed with `/timezone view`.", footer=footer, ephemeral=ctx.whisper)

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
            flaggy = country_code_to_emoji(country_code)

        await ctx.send_success(description=f"{member.mention}'s timezone is `{db_user.timezone}` {flaggy}\nIt is currently `{datetime.datetime.now(pytz.timezone(db_user.timezone)).strftime('%I:%M %p %Z')}`", ephemeral=ctx.whisper)

    @timezone.command(name="list", description="View a list of all timezones or timezones in your country")
    @app_commands.autocomplete(country_code=timezone_country_autocomplete)
    @transform_context
    @always_whisper
    async def _list(self, ctx: GIRContext, country_code: str = None):
        ctx.country_code = country_code
        if country_code is None:
            timezones = list(pytz.common_timezones_set)
            timezones.sort()
        else:
            timezones = pytz.country_timezones.get(country_code.upper())
            if timezones is None:
                raise commands.BadArgument(f"Country code `{country_code}` was not found!")

            timezones.sort()

        menu = Menu(ctx, timezones, per_page=15, page_formatter=format_tz_page, whisper=ctx.whisper)
        await menu.start()


async def setup(bot: commands.Bot):
    await bot.add_cog(Timezones(bot))
