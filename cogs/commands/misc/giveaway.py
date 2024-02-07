import datetime
import random
import pytz

import discord
import humanize
from data.model import Giveaway as GiveawayDB
from data.services import guild_service
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt
from utils import GIRContext, cfg, end_giveaway, transform_context
from utils.framework import admin_and_up
from utils.framework.transformers import Duration
from utils.views import time_suggestions


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.giveaway_messages = {}

    giveaway = app_commands.Group(name="giveaway", description="Interact with tags", guild_ids=[cfg.guild_id])

    @admin_and_up()
    @giveaway.command(description="Start a giveaway.")
    @app_commands.describe(prize="The prize to give away.")
    @app_commands.describe(sponsor="The sponsor of the giveaway.")
    @app_commands.describe(time="Duration of the giveaway")
    @app_commands.autocomplete(time=time_suggestions)
    @app_commands.describe(winners="The number of winners.",)
    @app_commands.describe(channel="The channel to send the giveaway in.")
    @transform_context
    async def start(self, ctx: GIRContext, prize: str, sponsor: discord.Member, time: Duration, winners: int, channel: discord.TextChannel):
        delta = time
        if delta is None:
            raise commands.BadArgument("Invalid time passed in.")

        if winners <= 0:
            raise commands.BadArgument("Must have more than 1 winner!")

        # calculate end time
        now = datetime.datetime.now(pytz.utc)
        end_time = now + datetime.timedelta(seconds=delta)

        # prepare giveaway embed and post it in giveaway channel
        embed = discord.Embed(title="New giveaway!")
        embed.description = f"**{prize}** is being given away by {sponsor.mention} to **{winners}** lucky {'winner' if winners == 1 else 'winners'}!"
        embed.add_field(name="Time remaining",
                        value=f"Expires {format_dt(end_time, style='R')}")
        embed.timestamp = end_time
        embed.color = discord.Color.random()
        embed.set_footer(text="Ends")

        message = await channel.send(embed=embed)
        await message.add_reaction('🎉')

        # store giveaway in database
        giveaway = GiveawayDB(
            _id=message.id,
            channel=channel.id,
            name=prize,
            winners=winners,
            end_time=end_time,
            sponsor=sponsor.id)
        giveaway.save()

        await ctx.send_success(f"Giveaway created!", delete_after=5)

        ctx.tasks.schedule_end_giveaway(
            channel_id=channel.id, message_id=message.id, date=end_time, winners=winners)

    @admin_and_up()
    @giveaway.command(description="Pick a new winner of an already ended giveaway.")
    @app_commands.describe(message_id="The ID of the giveaway message.")
    @transform_context
    async def reroll(self, ctx: GIRContext, message_id: str):
        g = guild_service.get_giveaway(_id=int(message_id))

        if g is None:
            raise commands.BadArgument(
                "Couldn't find an ended giveaway by the provided ID.")
        elif not g.is_ended:
            raise commands.BadArgument("That giveaway hasn't ended yet!")
        elif len(g.entries) == 0:
            raise commands.BadArgument(
                f"There are no entries for the giveaway of **{g.name}**.")
        elif len(g.entries) <= len(g.previous_winners):
            raise commands.BadArgument("No more winners are possible!")

        the_winner = None
        while the_winner is None:
            random_id = random.choice(g.entries)
            the_winner = ctx.guild.get_member(random_id)
            if the_winner is not None and the_winner.id not in g.previous_winners:
                break
            the_winner = None

        g.previous_winners.append(the_winner.id)
        g.save()

        channel = ctx.guild.get_channel(g.channel)

        await channel.send(f"**Reroll**\nThe new winner of the giveaway of **{g.name}** is {the_winner.mention}! Congratulations!")
        await ctx.send_success("Rerolled!", delete_after=5)

    @admin_and_up()
    @giveaway.command(description="End a giveaway early.")
    @app_commands.describe(message_id="The ID of the giveaway message.")
    @transform_context
    async def end(self, ctx: GIRContext, message_id: str):
        await ctx.defer()
        giveaway = guild_service.get_giveaway(_id=int(message_id))
        if giveaway is None:
            raise commands.BadArgument(
                "A giveaway with that ID was not found.")
        elif giveaway.is_ended:
            raise commands.BadArgument("That giveaway has already ended.")

        ctx.tasks.tasks.remove_job(str(int(message_id) + 2), 'default')
        await end_giveaway(giveaway.channel, message_id, giveaway.winners)

        await ctx.send_success("Giveaway ended!", delete_after=5)

    async def do_giveaway_update(self, giveaway: GiveawayDB, guild: discord.Guild):
        if giveaway is None:
            return
        if giveaway.is_ended:
            return

        now = datetime.datetime.now()
        end_time = giveaway.end_time
        if end_time is None or end_time < now:
            return

        channel = guild.get_channel(giveaway.channel)

        # caching mechanism for each giveaway message so we don't get ratelimited by discord
        if giveaway._id in self.giveaway_messages:
            message = self.giveaway_messages[giveaway._id]
        else:
            try:
                message = await channel.fetch_message(giveaway._id)
                self.giveaway_messages[giveaway._id] = message
            except Exception:
                return

        if len(message.embeds) == 0:
            return

        embed = message.embeds[0]
        embed.set_field_at(0, name="Time remaining",
                           value=f"Less than {humanize.naturaldelta(end_time - now)}")
        await message.edit(embed=embed)


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
