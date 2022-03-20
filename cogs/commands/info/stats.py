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
from utils.config import cfg
from utils import BlooContext
from utils.context import transform_context
from utils.logging import logger
from utils.permissions.checks import whisper


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Test server latency by measuring how long it takes to edit a message")
    @transform_context
    @whisper
    async def ping(self, ctx: BlooContext) -> None:
        print(ctx.whisper)
        embed = discord.Embed(
            title="Pong!", color=discord.Color.blurple())
        embed.set_thumbnail(url=self.bot.user.display_avatar)
        embed.description = "Latency: testing..."

        # measure time between sending a message and time it is posted
        b = datetime.utcnow()

        # TODO: fix whisper
        # await interaction.response.send_message(embed=embed, ephemeral=ctx.whisper)
        await ctx.respond(embed=embed)

        ping = floor((datetime.utcnow() - b).total_seconds() * 1000)
        embed.description = ""
        embed.add_field(name="Message Latency", value=f"`{ping}ms`")
        embed.add_field(name="API Latency",
                        value=f"`{floor(self.bot.latency*1000)}ms`")

        await ctx.edit(embed=embed)

    # # @whisper()
    # # @slash_command(guild_ids=[cfg.guild_id], description="Get number of users of a role")
    # @app_commands.guilds(cfg.guild_id)
    # @app_commands.command(description="Get number of users of a role")
    # async def roleinfo(self, interaction: discord.Interaction, role: Option(discord.Role, description="Role to view info of")) -> None:
    #     """Displays information about a specific role.

    #     Example usage
    #     -------------
    #     /roleinfo role:<role>

    #     Parameters
    #     ----------
    #     role : role
    #         "role to get information about"

    #     """
    #     embed = discord.Embed(title="Role Statistics")
    #     embed.description = f"{len(role.members)} members have role {role.mention}"
    #     embed.color = role.color

    #     await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    # @whisper()
    # @slash_command(guild_ids=[cfg.guild_id], description="Statistics about the bot")
    # async def stats(self, ctx: BlooContext) -> None:
    #     """Displays statistics about the bot.

    #     Example usage
    #     -------------
    #     /stats

    #     """
    #     process = psutil.Process(os.getpid())

    #     embed = discord.Embed(
    #         title=f"{self.bot.user.name} Statistics", color=discord.Color.blurple())
    #     embed.set_thumbnail(url=self.bot.user.display_avatar)
    #     embed.add_field(name="Bot started", value=format_dt(
    #         self.start_time, style='R'))
    #     embed.add_field(name="CPU Usage", value=f"{psutil.cpu_percent()}%")
    #     embed.add_field(name="Memory Usage",
    #                     value=f"{floor(process.memory_info().rss/1000/1000)} MB")
    #     embed.add_field(name="Python Version", value=platform.python_version())

    #     await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    # @whisper()
    # @slash_command(guild_ids=[cfg.guild_id], description="Displays info about the server")
    # async def serverinfo(self, ctx: BlooContext):
    #     """Displays info about the server.

    #     Example usage
    #     -------------
    #     /serverinfo

    #     """
    #     guild = ctx.guild
    #     embed = discord.Embed(title="Server Information",
    #                           color=discord.Color.blurple())
    #     embed.set_thumbnail(url=guild.icon)

    #     if guild.banner is not None:
    #         embed.set_image(url=guild.banner.url)

    #     embed.add_field(name="Emojis", value=len(guild.emojis), inline=True)
    #     embed.add_field(name="Boost Tier",
    #                     value=guild.premium_tier, inline=True)
    #     embed.add_field(name="Users", value=guild.member_count, inline=True)
    #     embed.add_field(name="Channels", value=len(
    #         guild.channels) + len(guild.voice_channels), inline=True)
    #     embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    #     embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    #     embed.add_field(
    #         name="Created", value=f"{format_dt(guild.created_at, style='F')} ({format_dt(guild.created_at, style='R')})", inline=True)

    #     await ctx.respond_or_edit(embed=embed, ephemeral=ctx.whisper)

    # @whisper()
    # @slash_command(guild_ids=[cfg.guild_id], description="Present statistics on who has been banned for raids.")
    # async def raidstats(self, ctx: BlooContext) -> None:
    #     """Present statistics on who has been banned for raids.
    #     """

    #     embed = discord.Embed(title="Raid Statistics",
    #                           color=discord.Color.blurple())
    #     raids = user_service.fetch_raids()

    #     total = 0
    #     for raid_type, cases in raids.items():
    #         total += cases
    #         embed.add_field(name=raid_type, value=f"{cases} cases.")

    #     embed.add_field(name="Total antiraid cases",
    #                     value=f"{total}", inline=False)
    #     await ctx.respond_or_edit(embed=embed, ephemeral=ctx.whisper)

    # @mod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Present statistics on cases by each mod.", permissions=slash_perms.mod_and_up())
    # async def casestats(self, ctx: BlooContext, mod: Option(discord.Member, required=False) = None) -> None:
    #     """Present statistics on cases by each mod.
    #     """
        
    #     if mod is None:
    #         mod = ctx.author

    #     embed = discord.Embed(color=discord.Color.blurple())
    #     embed.set_author(name=f"{mod}'s case statistics",
    #                      icon_url=mod.display_avatar)

    #     raids = user_service.fetch_cases_by_mod(mod.id)
    #     embed.add_field(name="Total cases", value=raids.get("total"))

    #     string = ""
    #     for reason, count in raids.get("counts")[:5]:
    #         string += f"**{reason}**: {count}\n"

    #     if string:
    #         embed.add_field(name="Top reasons", value=string, inline=False)

    #     await ctx.respond_or_edit(embed=embed)

    # @casestats.error
    # @raidstats.error
    # @ping.error
    # @roleinfo.error
    # @stats.error
    # @serverinfo.error
    # async def info_error(self,  ctx: BlooContext, error):
    #     if isinstance(error, discord.ApplicationCommandInvokeError):
    #         error = error.original

    #     if (isinstance(error, commands.MissingRequiredArgument)
    #         or isinstance(error, PermissionsFailure)
    #         or isinstance(error, commands.BadArgument)
    #         or isinstance(error, commands.BadUnionArgument)
    #         or isinstance(error, commands.MissingPermissions)
    #         or isinstance(error, commands.BotMissingPermissions)
    #         or isinstance(error, commands.MaxConcurrencyReached)
    #             or isinstance(error, commands.NoPrivateMessage)):
    #         await ctx.send_error(error)
    #     else:
    #         await ctx.send_error("A fatal error occured. Tell <@109705860275539968> about this.")
    #         logger.error(traceback.format_exc())


async def setup(bot):
    await bot.add_cog(Stats(bot))
