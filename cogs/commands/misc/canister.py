
import re

import discord
from discord import app_commands
from discord.ext import commands
from utils import GIRContext, canister_search_package, cfg, transform_context
from utils.fetchers import canister_fetch_repos
from utils.framework import gatekeeper, whisper_in_general, find_triggered_filters, find_triggered_raid_phrases
from utils.framework.filter import has_only_silent_filtered_words
from utils.views import TweakDropdown, default_repos, repo_autocomplete


class Canister(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.guild.id != cfg.guild_id:
            return

        author = message.guild.get_member(message.author.id)
        if author is None:
            return
        if not gatekeeper.has(message.guild, author, 5) and message.channel.id == cfg.channels.general:
            return

        pattern = re.compile(
            r".*?(?<!\[)+\[\[((?!\s+)([\w+\ \&\+\-\<\>\#\:\;\%\(\)]){2,})\]\](?!\])+.*")
        if not pattern.match(message.content):
            return
        
        if filter_words := await find_triggered_filters(message.content, message.author) or await find_triggered_raid_phrases(message.content, message.author):
            # if any of the triggered filtered words are not silently filtered, don't show results
            if not has_only_silent_filtered_words(filter_words):
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
    async def package(self, ctx: GIRContext, query: str) -> None:
        if len(query) < 2:
            raise commands.BadArgument("Please enter a longer query.")

        should_whisper = False
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and ctx.channel.id == cfg.channels.general:
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
    async def repo(self, ctx: GIRContext, query: str) -> None:
        repos = await canister_fetch_repos()
        matches = [repo for repo in repos if repo.get("slug") and repo.get(
            "slug") is not None and repo.get("slug").lower() == query.lower()]
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
        embed.set_thumbnail(url=f"{'https://stkc.win/assets/bigboss-sileo.png' if repo_data.get('name').lower() == 'bigboss' else repo_data.get('uri')+'/CydiaIcon.png'}")
        embed.set_footer(text="Powered by Canister")

        this_repo = repo_data.get("uri")
        view = discord.ui.View()
        for repo in default_repos:
            if repo in this_repo:
                [view.add_item(item) for item in [
                    discord.ui.Button(label='Cannot add default repo', emoji="<:Sileo:959128883498729482>",
                                      url=f'https://repos.slim.rocks/repo/?repoUrl={this_repo}&manager=sileo', disabled=True, style=discord.ButtonStyle.url, row=1),
                    discord.ui.Button(label='Cannot add default repo', emoji="<:Zeeb:959129860603801630>",
                                      url=f'https://repos.slim.rocks/repo/?repoUrl={this_repo}&manager=zebra', disabled=True, style=discord.ButtonStyle.url, row=1),
                    discord.ui.Button(label='Cannot add default repo', emoji="<:Add:947354227171262534>",
                                      url=f'https://repos.slim.rocks/repo/?repoUrl={this_repo}', style=discord.ButtonStyle.url, disabled=True, row=1)
                ]]
                break
        if not view.children:
            [view.add_item(item) for item in [
                discord.ui.Button(label='Add Repo to Sileo', emoji="<:Sileo:959128883498729482>",
                                  url=f'https://repos.slim.rocks/repo/?repoUrl={this_repo}&manager=sileo', style=discord.ButtonStyle.url, row=1),
                discord.ui.Button(label='Add Repo to Zebra', emoji="<:Zeeb:959129860603801630>",
                                  url=f'https://repos.slim.rocks/repo/?repoUrl={this_repo}&manager=zebra', style=discord.ButtonStyle.url, row=1),
                discord.ui.Button(label='Other Package Managers', emoji="<:Add:947354227171262534>",
                                  url=f'https://repos.slim.rocks/repo/?repoUrl={this_repo}', style=discord.ButtonStyle.url, row=1)
            ]]

        await ctx.respond(embed=embed, ephemeral=ctx.whisper, view=view)


async def setup(bot):
    await bot.add_cog(Canister(bot))
