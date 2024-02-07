import json
import os
import re
import traceback

import aiohttp
import discord
from discord.ext import commands

from utils import canister_fetch_repos, cfg, logger
from utils.framework import gatekeeper
from utils.views import default_repos


class RepoWatcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return
        if message.guild.id != cfg.guild_id:
            return
        if message.author.bot:
            return
        if message.channel.id == cfg.channels.general and not gatekeeper.has(message.guild, message.author, 5):
            return
        # Stops double messages when a package and repo URL are in the same message
        if 'sileo://package/' in message.content:
            return

        url = re.search(r'(https?://\S+)', message.content)
        if url is None:
            return

        repos = await canister_fetch_repos()
        repos = [repo['uri'].lower() for repo in repos if repo.get('uri')]

        potential_repo = url.group(0).rstrip("/").lower()
        if any(repo in potential_repo for repo in default_repos):
            return

        if potential_repo not in repos:
            return

        view = discord.ui.View()
        embed = discord.Embed(color=discord.Color.green())
        embed.description = f"You have sent a link to a repo, you can use the buttons below to open it directly in your preferred package manager."
        view.add_item(discord.ui.Button(label='Add Repo to Sileo', emoji="<:Sileo:959128883498729482>",
                                        url=f"https://repos.slim.rocks/repo/?repoUrl={potential_repo}&manager=sileo", style=discord.ButtonStyle.url))
        view.add_item(discord.ui.Button(label='Add Repo to Zebra', emoji="<:Zeeb:959129860603801630>",
                                        url=f"https://repos.slim.rocks/repo/?repoUrl={potential_repo}&manager=zebra", style=discord.ButtonStyle.url))
        view.add_item(discord.ui.Button(label='Other Package Managers', emoji="<:Add:947354227171262534>",
                                        url=f"https://repos.slim.rocks/repo/?repoUrl={potential_repo}", style=discord.ButtonStyle.url))
        await message.reply(embed=embed, view=view, mention_author=False)


class Tweaks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not ("apt" in message.content.lower() and "base structure" in message.content.lower() and ("libhooker" or "substitute" or "substrate" in message.content.lower()) and len(message.content.splitlines()) >= 50):
            return

        async with aiohttp.ClientSession(headers={'content-type': 'application/json', 'X-Auth-Token': os.environ.get("PASTEE_TOKEN")}) as session:
            async with session.post(url='https://api.paste.ee/v1/pastes', json={"description": f"Uploaded by {message.author}", "sections": [{"name": f"Uploaded by {message.author}", "syntax": "text", "contents": message.content}]}) as response:
                if response.status != 201:
                    try:
                        raise Exception(
                            f"Failed to upload paste: {response.status}")
                    except Exception:
                        logger.error(traceback.format_exc())

                resp = await response.json()
                pastelink = resp.get("link")
                if pastelink is None:
                    return

                embed = discord.Embed(
                    title=f"Tweak list", color=discord.Color.green())
                embed.description = f"You have pasted a tweak list, to reduce chat spam it can be viewed [here]({pastelink})."

                await message.delete()
                await message.channel.send(message.author.mention, embed=embed)


class Sileo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return
        if message.guild.id != cfg.guild_id:
            return
        if message.author.bot:
            return
        if message.channel.id == cfg.channels.general and not gatekeeper.has(message.guild, message.author, 5):
            return

        urlscheme = re.search(
            "(sileo|zbra):\/\/package\/([a-zA-Z0-9]+(\.[a-zA-Z0-9]+)+(\.[a-zA-Z0-9]+)+)", message.content)

        if urlscheme is None:
            return

        view = discord.ui.View()
        embed = discord.Embed(color=discord.Color.green())
        embed.description = f"You have sent a link to a package, you can use the buttons below to open it directly in your preferred package manager."
        view.add_item(discord.ui.Button(label='View Package in Sileo', emoji="<:Sileo:959128883498729482>",
                                        url=f"https://sharerepo.stkc.win/v3/?pkgid={urlscheme.group(1)}", style=discord.ButtonStyle.url))
        view.add_item(discord.ui.Button(label='View Package in Zebra', emoji="<:Zeeb:959129860603801630>",
                                        url=f"https://sharerepo.stkc.win/v3/?pkgid={urlscheme.group(1)}&pkgman=zebra", style=discord.ButtonStyle.url))
        await message.reply(embed=embed, view=view, mention_author=False)


async def setup(bot):
    if os.environ.get("PASTEE_TOKEN") is None:
        logger.warn(
            "Pastee token not set, not loading the TweakList cog! If you want this, refer to README.md.")
        return

    await bot.add_cog(Tweaks(bot))
    await bot.add_cog(RepoWatcher(bot))
    await bot.add_cog(Sileo(bot))
