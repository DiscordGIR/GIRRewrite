from datetime import datetime

import pytz
from data.services import guild_service, user_service
from discord.ext import commands, tasks

from utils import GIRContext, cfg
from utils.framework import MONTH_MAPPING, give_user_birthday_role, whisper, gatekeeper
from utils.views import date_autocompleter


class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.eastern_timezone = pytz.timezone('US/Eastern')
        self.birthday.start()

    def cog_unload(self):
        self.birthday.cancel()

    @tasks.loop(seconds=120)
    async def birthday(self):
        """Background task to scan database for users whose birthday it is today.
        If it's someone's birthday, the bot will assign them the birthday role for 24 hours."""

        # assign the role at 12am US Eastern time
        eastern = pytz.timezone('US/Eastern')
        today = datetime.today().astimezone(eastern)
        # the date we will check for in the database
        date = [today.month, today.day]
        # get list of users whose birthday it is today
        birthdays = await user_service.retrieve_birthdays(date)

        guild = self.bot.get_guild(cfg.guild_id)
        if not guild:
            return

        # give each user whose birthday it is today the birthday role
        for person in birthdays:
            if person.birthday_excluded:
                continue

            user = guild.get_member(person._id)
            if user is None:
                return

            await give_user_birthday_role(self.bot, user, guild)


async def setup(bot):
    await bot.add_cog(Birthday(bot))
