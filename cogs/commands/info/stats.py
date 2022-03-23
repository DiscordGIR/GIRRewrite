import os
import platform
import traceback
from datetime import datetime
from math import floor

import discord
import psutil
from data.services.user_service import user_service
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt
from utils import BlooContext, cfg, logger, transform_context
from utils.framework import whisper, mod_and_up


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.now()

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Test server latency by measuring how long it takes to edit a message")
    @mod_and_up()
    @transform_context
    @whisper
    async def ping(self, ctx: BlooContext) -> None:
        embed = discord.Embed(
            title="Pong!", color=discord.Color.blurple())
        embed.set_thumbnail(url=self.bot.user.display_avatar)
        embed.description = "Latency: testing..."

        # measure time between sending a message and time it is posted
        b = datetime.utcnow()

        await ctx.respond_or_edit(embed=embed, ephemeral=ctx.whisper)

        ping = floor((datetime.utcnow() - b).total_seconds() * 1000)
        embed.description = ""
        embed.add_field(name="Message Latency", value=f"`{ping}ms`")
        embed.add_field(name="API Latency",
                        value=f"`{floor(self.bot.latency*1000)}ms`")

        await ctx.respond_or_edit(embed=embed)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get number of users of a role")
    @app_commands.describe(role="The role's ID")
    @transform_context
    @whisper
    async def roleinfo(self, ctx: BlooContext, role: discord.Role) -> None:
        embed = discord.Embed(title="Role Statistics")
        embed.description = f"{len(role.members)} members have role {role.mention}"
        embed.color = role.color

        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Statistics about the bot")
    @transform_context
    @whisper
    async def stats(self, ctx: BlooContext) -> None:
        process = psutil.Process(os.getpid())

        embed = discord.Embed(
            title=f"{self.bot.user.name} Statistics", color=discord.Color.blurple())
        embed.set_thumbnail(url=self.bot.user.display_avatar)
        embed.add_field(name="Bot started", value=format_dt(
            self.start_time, style='R'))
        embed.add_field(name="CPU Usage", value=f"{psutil.cpu_percent()}%")
        embed.add_field(name="Memory Usage",
                        value=f"{floor(process.memory_info().rss/1000/1000)} MB")
        embed.add_field(name="Python Version", value=platform.python_version())

        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Displays info about the server")
    @transform_context
    async def serverinfo(self, ctx: BlooContext):
        guild = ctx.guild
        embed = discord.Embed(title="Server Information",
                              color=discord.Color.blurple())
        embed.set_thumbnail(url=guild.icon)

        if guild.banner is not None:
            embed.set_image(url=guild.banner.url)

        embed.add_field(name="Emojis", value=len(guild.emojis), inline=True)
        embed.add_field(name="Boost Tier",
                        value=guild.premium_tier, inline=True)
        embed.add_field(name="Users", value=guild.member_count, inline=True)
        embed.add_field(name="Channels", value=len(
            guild.channels) + len(guild.voice_channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        # TODO: use ban cache
        embed.add_field(name="Bans", value=len(await guild.bans()), inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(
            name="Created", value=f"{format_dt(guild.created_at, style='F')} ({format_dt(guild.created_at, style='R')})", inline=True)

        await ctx.respond_or_edit(embed=embed, ephemeral=ctx.whisper)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Present statistics on who has been banned for raids.")
    @transform_context
    async def raidstats(self, ctx: BlooContext) -> None:
        embed = discord.Embed(title="Raid Statistics",
                              color=discord.Color.blurple())
        raids = user_service.fetch_raids()

        total = 0
        for raid_type, cases in raids.items():
            total += cases
            embed.add_field(name=raid_type, value=f"{cases} cases.")

        embed.add_field(name="Total antiraid cases",
                        value=f"{total}", inline=False)
        await ctx.respond_or_edit(embed=embed, ephemeral=ctx.whisper)

    # @mod_and_up() #TODO: Fix
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Present statistics on cases by each mod.")
    @app_commands.describe(mod="Moderator to view statistics of")
    @transform_context
    @whisper
    async def casestats(self, ctx: BlooContext, mod: discord.Member = None) -> None:
        if mod is None:
            mod = ctx.author

        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(name=f"{mod}'s case statistics",
                         icon_url=mod.display_avatar)

        raids = user_service.fetch_cases_by_mod(mod.id)
        embed.add_field(name="Total cases", value=raids.get("total"))

        string = ""
        for reason, count in raids.get("counts")[:5]:
            string += f"**{reason}**: {count}\n"

        if string:
            embed.add_field(name="Top reasons", value=string, inline=False)

        await ctx.respond_or_edit(embed=embed)


async def setup(bot):
    await bot.add_cog(Stats(bot))
