import json
import os
import re
import traceback

import aiohttp
import discord
from data.services.guild_service import guild_service
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
        if message.channel.id == (await guild_service.get_guild()).channel_general and not gatekeeper.has(message.guild, message.author, 5):
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

        view.add_item(discord.ui.Button(label='Add Repo to Sileo', emoji="<:Sileo:959128883498729482>",
                                        url=f"https://repos.slim.rocks/repo/?repoUrl={potential_repo}&manager=sileo", style=discord.ButtonStyle.url))
        view.add_item(discord.ui.Button(label='Add Repo to Zebra', emoji="<:Zeeb:959129860603801630>",
                                        url=f"https://repos.slim.rocks/repo/?repoUrl={potential_repo}&manager=zebra", style=discord.ButtonStyle.url))
        view.add_item(discord.ui.Button(label='Other Package Managers', emoji="<:Add:947354227171262534>",
                                        url=f"https://repos.slim.rocks/repo/?repoUrl={potential_repo}", style=discord.ButtonStyle.url))

        await message.reply(file=discord.File("data/images/transparent1x1.png"), view=view, mention_author=False)


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
        if message.channel.id == (await guild_service.get_guild()).channel_general and not gatekeeper.has(message.guild, message.author, 5):
            return

        urlscheme = re.search(
            "sileo:\/\/package\/([a-zA-Z0-9]+(\.[a-zA-Z0-9]+)+(\.[a-zA-Z0-9]+)+)", message.content)
        if urlscheme is None:
            return

        async with aiohttp.ClientSession() as client:
            async with client.get(f'https://api.canister.me/v1/community/packages/search?query={urlscheme.group(1)}&searchFields=identifier&responseFields=name,repository.uri,repository.name,depiction,packageIcon,tintColor') as resp:
                if resp.status == 200:
                    response = json.loads(await resp.text())
                data = response.get('data')

                if not data:
                    view = discord.ui.View()
                    embed = discord.Embed(
                        title=":(\nI couldn't find that package", color=discord.Color.orange())
                    embed.description = f"You have sent a link to a package, you can use the button below to open it directly in Sileo."
                    view.add_item(discord.ui.Button(label='View Package in Sileo', emoji="<:Search2:947525874297757706>",
                                                    url=f"https://sharerepo.stkc.win/v3/?pkgid={urlscheme.group(1)}", style=discord.ButtonStyle.url))
                    await message.reply(embed=embed, view=view, mention_author=False)
                    return

                canister = response['data'][0]
                color = canister.get('tintColor')
                view = discord.ui.View()

                if color is None:
                    color = discord.Color.blue()

                else:
                    color = discord.Color(int(color.strip('#'), 16))
                embed = discord.Embed(
                    title=f"{canister.get('name')} - {canister.get('repository')['name']}", color=color)
                embed.description = f"You have sent a link to a package, you can use the button below to open it directly in Sileo."
                icon = canister.get('packageIcon')
                depiction = canister.get('depiction')
                view.add_item(discord.ui.Button(label='View Package in Sileo', emoji="<:Search2:947525874297757706>",
                                                url=f"https://sharerepo.stkc.win/v3/?pkgid={urlscheme.group(1)}", style=discord.ButtonStyle.url))

                if depiction is not None:
                    view.add_item(discord.ui.Button(label='View Depiction', emoji="<:Depiction:947358756033949786>", url=canister.get(
                        'depiction'), style=discord.ButtonStyle.url))

                if icon is not None:
                    embed.set_thumbnail(url=canister.get('packageIcon'))

                view.add_item(discord.ui.Button(label='Add Repo to Sileo', emoji="<:Sileo:959128883498729482>",
                                                url=f"https://repos.slim.rocks/repo/?repoUrl={canister.get('repository')['uri']}&manager=sileo", style=discord.ButtonStyle.url))
                await message.reply(embed=embed, view=view, mention_author=False)


async def setup(bot):
    if os.environ.get("PASTEE_TOKEN") is None:
        logger.warn(
            "Pastee token not set, not loading the TweakList cog! If you want this, refer to README.md.")
        return

    await bot.add_cog(Tweaks(bot))
    await bot.add_cog(RepoWatcher(bot))
    await bot.add_cog(Sileo(bot))
