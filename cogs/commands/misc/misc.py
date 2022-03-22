import base64
import datetime
import io
import json
from turtle import title
from typing import Union

import aiohttp
import discord
import pytimeparse
from data.services import guild_service
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt
from PIL import Image
from utils import BlooContext, cfg
from utils.context import transform_context
# from utils.menu import BypassMenu
from utils.framework import (PermissionsFailure, gatekeeper, mod_and_up,
                             whisper, whisper_in_general)
# from utils.views import bypass_autocomplete, get_ios_cfw, rule_autocomplete
from yarl import URL

from utils.views import PFPButton, PFPView, rule_autocomplete


# class BypassDropdown(discord.ui.Select):
#     def __init__(self, ctx, apps):
#         self.ctx = ctx
#         self.apps = {app.get("bundleId"): app for app in apps}
#         options = [
#             discord.SelectOption(label=app.get("name"), value=app.get("bundleId"), description="Bypasses found" if app.get("bypasses") else "No bypasses found", emoji='<:appstore:392027597648822281>') for app in apps
#         ]
#         super().__init__(placeholder='Pick an app...',
#                          min_values=1, max_values=1, options=options)

#     async def callback(self, interaction):
#         if interaction.user != self.ctx.author:
#             return

#         self.view.stop()
#         app = self.apps.get(self.values[0])
#         self.ctx.app = app
#         if not app.get("bypasses"):
#             await self.ctx.send_error("No bypasses found for this app!")
#             return

#         menu = BypassMenu(self.ctx, app.get("bypasses"), per_page=1,
#                           page_formatter=format_bypass_page, whisper=self.ctx.whisper)
#         await menu.start()

#     async def on_timeout(self):
#         self.disabled = True
#         self.placeholder = "Timed out"

#         await self.ctx.edit(view=self._view)


def format_bypass_page(ctx, entries, current_page, all_pages):
    ctx.current_bypass = entries[0]
    embed = discord.Embed(title=ctx.app.get(
        "name"), color=discord.Color.blue())
    embed.set_thumbnail(url=ctx.app.get("icon"))

    embed.description = f"You can use **{ctx.current_bypass.get('name')}**!"
    if ctx.current_bypass.get("notes") is not None:
        embed.add_field(name="Note", value=ctx.current_bypass.get('notes'))
        embed.color = discord.Color.orange()
    if ctx.current_bypass.get("version") is not None:
        embed.add_field(name="Supported versions",
                        value=f"This bypass works on versions {ctx.current_bypass.get('version')} of the app")

    embed.set_footer(
        text=f"Powered by ios.cfw.guide • Bypass {current_page} of {len(all_pages)}")
    return embed


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_cooldown = commands.CooldownMapping.from_cooldown(
            3, 15.0, commands.BucketType.channel)

        try:
            with open('emojis.json') as f:
                self.emojis = json.loads(f.read())
        except:
            raise Exception(
                "Could not find emojis.json. Make sure to run scrape_emojis.py")

    # TODO: duration transformer
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Send yourself a reminder after a given time gap")
    @app_commands.describe(reminder="What do you want to be reminded of?")
    @app_commands.describe(duration="When do we remind you? (i.e 1m, 1h, 1d)")
    @transform_context
    @whisper
    async def remindme(self, ctx: BlooContext, reminder: str, duration: str):
        now = datetime.datetime.now()
        delta = pytimeparse.parse(duration)
        if delta is None:
            raise commands.BadArgument(
                "Please give me a valid time to remind you! (i.e 1h, 30m)")

        time = now + datetime.timedelta(seconds=delta)
        if time < now:
            raise commands.BadArgument("Time has to be in the future >:(")
        reminder = discord.utils.escape_markdown(reminder)

        ctx.tasks.schedule_reminder(ctx.author.id, reminder, time)
        await ctx.send_success(title="Reminder set", description=f"We'll remind you {discord.utils.format_dt(time, style='R')}", delete_after=5)

    # TODO: emoji transformer
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Post large version of a given emoji")
    @app_commands.describe(emoji="The emoji you want to get the large version of")
    @transform_context
    async def jumbo(self, ctx: BlooContext, emoji: str):
        # non-mod users will be ratelimited
        bot_chan = guild_service.get_guild().channel_botspam
        if not gatekeeper.has(ctx.guild, ctx.author, 5) and ctx.channel.id != bot_chan:
            bucket = self.spam_cooldown.get_bucket(ctx.interaction)
            if bucket.update_rate_limit():
                raise commands.BadArgument("This command is on cooldown.")

        # is this a regular Unicode emoji?
        try:
            em = await commands.PartialEmojiConverter().convert(ctx, emoji)
        except commands.PartialEmojiConversionFailure:
            em = emoji
        if isinstance(em, str):
            async with ctx.typing():
                emoji_url_file = self.emojis.get(em)
                if emoji_url_file is None:
                    raise commands.BadArgument(
                        "Couldn't find a suitable emoji.")

            im = Image.open(io.BytesIO(base64.b64decode(emoji_url_file)))
            image_conatiner = io.BytesIO()
            im.save(image_conatiner, 'png')
            image_conatiner.seek(0)
            _file = discord.File(image_conatiner, filename='image.png')
            await ctx.respond(file=_file)
        else:
            await ctx.respond(em.url)

    # TODO: do this as buttons?
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get avatar of another user or yourself.")
    @app_commands.describe(user="The user you want to get the avatar of")
    @transform_context
    @whisper
    async def avatar(self, ctx: BlooContext, user: Union[discord.Member, discord.User] = None) -> None:
        if user is None:
            user = ctx.author

        await self.handle_avatar(ctx, user)

#     @whisper()
#     @user_command(guild_ids=[cfg.guild_id], name="View avatar")
#     async def avatar_rc(self, ctx: BlooContext, member: discord.Member):
#         await self.handle_avatar(ctx, member)

#     @whisper()
#     @message_command(guild_ids=[cfg.guild_id], name="View avatar")
#     async def avatar_msg(self, ctx: BlooContext, message: discord.Message):
#         await self.handle_avatar(ctx, message.author)

    async def handle_avatar(self, ctx, user: Union[discord.Member, discord.User]):
        embed = discord.Embed(title=f"{user}'s avatar")
        animated = ["gif", "png", "jpeg", "webp"]
        not_animated = ["png", "jpeg", "webp"]

        avatar = user.avatar or user.default_avatar

        def fmt(format_):
            return f"[{format_}]({avatar.replace(format=format_, size=4096)})"

        if user.display_avatar.is_animated():
            embed.description = f"View As\n {'  '.join([fmt(format_) for format_ in animated])}"
        else:
            embed.description = f"View As\n {'  '.join([fmt(format_) for format_ in not_animated])}"

        embed.set_image(url=avatar.replace(size=4096))
        embed.color = discord.Color.random()

        view = discord.utils.MISSING
        if isinstance(user, discord.Member) and user.guild_avatar is not None:
            view = PFPView(ctx, embed)
            view.add_item(PFPButton(ctx, user))

        view.message = await ctx.respond(embed=embed, ephemeral=ctx.whisper, view=view)

    # TODO: move to ios.cfw.guide cog
#     @whisper_in_general()
#     @slash_command(guild_ids=[cfg.guild_id], description="Find out how to bypass jailbreak detection for an app")
#     async def bypass(self, ctx: BlooContext, app: Option(str, description="Name of the app", autocomplete=bypass_autocomplete)):
#         await ctx.defer(ephemeral=ctx.whisper)
#         data = await get_ios_cfw()
#         bypasses = data.get('bypass')
#         matching_apps = [body for _, body in bypasses.items(
#         ) if app.lower() in body.get("name").lower()]

#         if not matching_apps:
#             raise commands.BadArgument(
#                 "The API does not recognize that app or there are no bypasses available.")

#         # matching_app = bypasses[matching_apps[0]]
#         # print(matching_app)
#         if len(matching_apps) > 1:
#             view = discord.ui.View(timeout=30)
#             apps = matching_apps[:25]
#             apps.sort(key=lambda x: x.get("name"))
#             menu = BypassDropdown(ctx, apps)
#             view.add_item(menu)
#             view.on_timeout = menu.on_timeout
#             embed = discord.Embed(
#                 description="Which app would you like to view bypasses for?", color=discord.Color.blurple())
#             await ctx.respond(embed=embed, view=view, ephemeral=ctx.whisper)
#         else:
#             ctx.app = matching_apps[0]
#             bypasses = ctx.app.get("bypasses")
#             if not bypasses or bypasses is None or bypasses == [None]:
#                 raise commands.BadArgument(
#                     f"{ctx.app.get('name')} has no bypasses.")

#             menu = BypassMenu(ctx, ctx.app.get(
#                 "bypasses"), per_page=1, page_formatter=format_bypass_page, whisper=ctx.whisper)
#             await menu.start()

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Post the embed for one of the rules")
    @app_commands.describe(title="The rule you want to view")
    @app_commands.autocomplete(title=rule_autocomplete)
    @app_commands.describe(user_to_mention="User to mention in response")
    @transform_context
    async def rule(self, ctx: BlooContext, title: str, user_to_mention: discord.Member = None):
        if title not in self.bot.rule_cache.cache:
            potential_rules = [r for r in self.bot.rule_cache.cache if title.lower() == r.lower(
            ) or title.strip() == f"{r} - {self.bot.rule_cache.cache[r].description}"[:100].strip()]
            if not potential_rules:
                raise commands.BadArgument(
                    "Rule not found! Title must match one of the embeds exactly, use autocomplete to help!")
            title = potential_rules[0]

        embed = self.bot.rule_cache.cache[title]

        if user_to_mention is not None:
            title = f"Hey {user_to_mention.mention}, have a look at this!"
        else:
            title = None

        await ctx.respond_or_edit(content=title, embed=embed)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get the topic for a channel")
    @app_commands.describe(channel="Channel to get the topic for")
    @app_commands.describe(user_to_mention="User to mention in response")
    @transform_context
    async def topic(self, ctx: BlooContext, channel: discord.TextChannel = None, user_to_mention: discord.Member = None):
        channel = channel or ctx.channel
        if channel.topic is None:
            raise commands.BadArgument(f"{channel.mention} has no topic!")

        if user_to_mention is not None:
            title = f"Hey {user_to_mention.mention}, have a look at this!"
        else:
            title = None

        embed = discord.Embed(title=f"#{channel.name}'s topic",
                              description=channel.topic, color=discord.Color.blue())
        await ctx.respond_or_edit(content=title, embed=embed)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Start a poll")
    @app_commands.describe(question="Question to ask")
    @app_commands.describe(channel="Channel to post the poll in")
    @transform_context
    async def poll(self, ctx: BlooContext, question: str, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        embed = discord.Embed(description=question,
                              color=discord.Color.random())
        embed.timestamp = datetime.datetime.now()
        embed.set_footer(text=f"Poll started by {ctx.author}")
        message = await channel.send(embed=embed)

        emojis = ['⬆️', '⬇️']

        for emoji in emojis:
            await message.add_reaction(emoji)

        ctx.whisper = True
        await ctx.send_success("Done!")

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="View the status of various Discord features")
    @transform_context
    @whisper
    async def dstatus(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discordstatus.com/api/v2/components.json") as resp:
                if resp.status == 200:
                    components = await resp.json()

        async with aiohttp.ClientSession() as session:
            async with session.get("https://discordstatus.com/api/v2/incidents.json") as resp:
                if resp.status == 200:
                    incidents = await resp.json()

        api_status = components.get('components')[
            0].get('status').title()  # API
        mp_status = components.get('components')[4].get(
            'status').title()  # Media Proxy
        pn_status = components.get('components')[6].get(
            'status').title()  # Push Notifications
        s_status = components.get('components')[8].get(
            'status').title()  # Search
        v_status = components.get('components')[11].get(
            'status').title()  # Voice
        cf_status = components.get('components')[2].get(
            'status').title()  # Cloudflare

        title = "All Systems Operational" if api_status == "Operational" and mp_status == "Operational" and pn_status == "Operational" and s_status == "Operational" and v_status == "Operational" and cf_status == "Operational" else "Known Incident"
        color = discord.Color.green(
        ) if title == "All Systems Operational" else discord.Color.orange()

        last_incident = incidents.get('incidents')[0].get('name')
        last_status = incidents.get('incidents')[0].get('status').title()
        last_created = datetime.datetime.strptime(incidents.get(
            'incidents')[0].get('created_at'), "%Y-%m-%dT%H:%M:%S.%f%z")
        last_update = datetime.datetime.strptime(incidents.get(
            'incidents')[0].get('updated_at'), "%Y-%m-%dT%H:%M:%S.%f%z")
        last_impact = incidents.get('incidents')[0].get('impact')

        online = '<:status_online:942288772551278623>'
        offline = '<:status_dnd:942288811818352652>'

        incident_icons = {'none': '<:status_offline:942288832051679302>',
                          'maintenance': '<:status_total:942290485916073995>',
                          'minor': '<:status_idle:942288787000680499>',
                          'major': '<:status_dnd:942288811818352652>',
                          'critical': '<:status_dnd:942288811818352652>'}

        embed = discord.Embed(title=title, description=f"""
{online if api_status == 'Operational' else offline} **API:** {api_status}
{online if mp_status == 'Operational' else offline} **Media Proxy:** {mp_status}
{online if pn_status == 'Operational' else offline} **Push Notifications:** {pn_status}
{online if s_status == 'Operational' else offline} **Search:** {s_status}
{online if v_status == 'Operational' else offline} **Voice:** {v_status}
{online if cf_status == 'Operational' else offline} **Cloudflare:** {cf_status}

__**Last outage information**__
**Incident:** {incident_icons.get(last_impact)} {last_incident}
**Status:** {online if last_status == 'Resolved' else offline} {last_status}
**Identified at:** {format_dt(last_created, style='F')}
**{'Resolved at' if last_status == 'Resolved' else 'Last updated'}:** {format_dt(last_update, style='F')}
        """, color=color)
        embed.set_footer(text="Powered by discordstatus.com")
        await ctx.respond(embed=embed, ephemeral=ctx.whisper)


async def setup(bot):
    await bot.add_cog(Misc(bot))
