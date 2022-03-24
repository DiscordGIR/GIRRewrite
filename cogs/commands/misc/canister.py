
import queue
import re

import discord
from data.services.guild_service import guild_service
from discord import app_commands
from discord.ext import commands
from utils import cfg, BlooContext, transform_context, canister_search_package
from utils.fetchers import canister_fetch_repos
from utils.framework import gatekeeper
from utils.framework.checks import whisper_in_general
from utils.views import default_repos, TweakMenu, TweakDropdown
from utils.views.autocompleters import repo_autocomplete


class Canister(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return

        author = message.guild.get_member(message.author.id)
        if author is None:
            return

        if not gatekeeper.has(message.guild, author, 5) and message.channel.id == guild_service.get_guild().channel_general:
            return

        pattern = re.compile(
            r".*?(?<!\[)+\[\[((?!\s+)([\w+\ \&\+\-\<\>\#\:\;\%\(\)]){2,})\]\](?!\])+.*")
        if not pattern.match(message.content):
            return

        matches = pattern.findall(message.content)
        if not matches:
            return

        search_term = matches[0][0].replace('[[', '').replace(']]', '')
        if not search_term:
            return

        ctx = await self.bot.get_context(message)

        async with ctx.typing():
            result = list(await canister_search_package(search_term))

        if not result:
            embed = discord.Embed(
                title=":(\nI couldn't find that package", color=discord.Color.red())
            embed.description = f"Try broadening your search query."
            await ctx.send(embed=embed, delete_after=8)
            return

        view = discord.ui.View(timeout=30)
        td = TweakDropdown(author, result, interaction=False,
                           should_whisper=False)
        view.add_item(td)
        td.refresh_view(result[0])
        view.on_timeout = td.on_timeout
        message = await ctx.send(embed=await td.format_tweak_page(result[0]), view=view)
        new_ctx = await self.bot.get_context(message)
        td.start(new_ctx)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Search for a jailbreak tweak or package")
    @app_commands.describe(query="Name of package to search for")
    @transform_context
    async def package(self, ctx: BlooContext, query: str) -> None:
        if len(query) < 2:
            raise commands.BadArgument("Please enter a longer query.")

        should_whisper = False
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and ctx.channel.id == guild_service.get_guild().channel_general:
            should_whisper = True

        await ctx.defer(ephemeral=should_whisper)
        result = list(await canister_search_package(query))

        if not result:
            embed = discord.Embed(
                title=":(\nI couldn't find that package", color=discord.Color.red())
            embed.description = f"Try broadening your search query."
            await ctx.respond(embed=embed)
            return

        view = discord.ui.View(timeout=30)
        td = TweakDropdown(ctx.author, result, interaction=True,
                           should_whisper=should_whisper)
        view.on_timeout = td.on_timeout
        view.add_item(td)
        td.refresh_view(result[0])
        await ctx.respond(embed=await td.format_tweak_page(result[0]), view=view)
        td.start(ctx)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Search for a tweak repository")
    @app_commands.describe(query="Name of repository to search for")
    @app_commands.autocomplete(query=repo_autocomplete)
    @transform_context
    @whisper_in_general
    async def repo(self, ctx: BlooContext, query: str) -> None:
        repos = await canister_fetch_repos()
        matches = [repo for repo in repos if repo.get("slug") and repo.get("slug") is not None and repo.get("slug").lower() == query.lower()]
        if not matches:
            await ctx.send_error("That repository isn't registered with Canister's database.")
            return

        repo_data = matches[0]

        for repo in default_repos:
            if repo in repo_data.get('uri'):
                ctx.repo = None
                break

        embed = discord.Embed(title=repo_data.get(
            'name'), color=discord.Color.blue())
        embed.add_field(name="URL", value=repo_data.get('uri'), inline=True)
        embed.add_field(name="Version", value=repo_data.get(
            'version'), inline=True)

        embed.set_thumbnail(url=f'{repo_data.get("uri")}/CydiaIcon.png')
        embed.set_footer(text="Powered by Canister")

        await ctx.respond(embed=embed)

async def setup(bot):
    await bot.add_cog(Canister(bot))
