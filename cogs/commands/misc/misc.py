import base64
import datetime
import io
import json
from typing import Union

import discord
import pytz
from data.services import guild_service, user_service
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt
from PIL import Image
from utils import (BlooContext, cfg, get_dstatus_components,
                   get_dstatus_incidents, transform_context)
from utils.framework import (MONTH_MAPPING, Duration, gatekeeper,
                             give_user_birthday_role, mod_and_up, whisper)
from utils.views import (PFPButton, PFPView, date_autocompleter,
                         rule_autocomplete)


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.eastern_timezone = pytz.timezone('US/Eastern')
        self.spam_cooldown = commands.CooldownMapping.from_cooldown(
            3, 15.0, commands.BucketType.channel)

        try:
            with open('emojis.json') as f:
                self.emojis = json.loads(f.read())
        except:
            raise Exception(
                "Could not find emojis.json. Make sure to run scrape_emojis.py")

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Send yourself a reminder after a given time gap")
    @app_commands.describe(reminder="What do you want to be reminded of?")
    @app_commands.describe(duration="When do we remind you? (i.e 1m, 1h, 1d)")
    @transform_context
    @whisper
    async def remindme(self, ctx: BlooContext, reminder: str, duration: Duration):
        now = datetime.datetime.now()
        delta = duration
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

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Set your birthday. The birthday role will be given to you on that day.")
    @app_commands.describe(month="The month you were born in")
    @app_commands.choices(month=[app_commands.Choice(name=m, value=m) for m in MONTH_MAPPING.keys()])
    @app_commands.describe(date="The date you were born on")
    @app_commands.autocomplete(date=date_autocompleter)
    @transform_context
    @whisper
    async def mybirthday(self, ctx: BlooContext, month: str, date: int) -> None:
        user = ctx.author
        if not (gatekeeper.has(ctx.guild, ctx.author, 1) or user.premium_since is not None):
            raise commands.BadArgument(
                "You need to be at least Member+ or a Nitro booster to use that command.")

        month = MONTH_MAPPING.get(month)
        if month is None:
            raise commands.BadArgument("You gave an invalid date")

        month = month["value"]

        # ensure date is real (2020 is a leap year in case the birthday is leap day)
        try:
            datetime.datetime(year=2020, month=month, day=date, hour=12)
        except ValueError:
            raise commands.BadArgument("You gave an invalid date.")

        # fetch user profile from DB
        db_user = user_service.get_user(user.id)

        # mods are able to ban users from using birthdays, let's handle that
        if db_user.birthday_excluded:
            raise commands.BadArgument("You are banned from birthdays.")

        # if the user already has a birthday set in the database, refuse to change it (if not a mod)
        if db_user.birthday != [] and not gatekeeper.has(ctx.guild, ctx.author, 5):
            raise commands.BadArgument(
                "You already have a birthday set! You need to ask a mod to change it.")

        # passed all the sanity checks, let's save the birthday
        db_user.birthday = [month, date]
        db_user.save()

        await ctx.send_success(f"Your birthday was set.")
        # if it's the user's birthday today let's assign the role right now!
        today = datetime.datetime.today().astimezone(self.eastern_timezone)
        if today.month == month and today.day == date:
            db_guild = guild_service.get_guild()
            await give_user_birthday_role(self.bot, db_guild, ctx.author, ctx.guild)

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Get avatar of another user or yourself.")
    @app_commands.describe(user="The user you want to get the avatar of")
    @transform_context
    @whisper
    async def avatar(self, ctx: BlooContext, user: Union[discord.Member, discord.User] = None) -> None:
        if user is None:
            user = ctx.author

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
        components = await get_dstatus_components()
        incidents = await get_dstatus_incidents()

        if not components or not incidents:
            raise commands.BadArgument(
                "Couldn't get Discord status information!")

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
