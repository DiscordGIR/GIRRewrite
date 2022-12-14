import os
import random
from datetime import datetime

import discord
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from data.model import Case
from data.services import guild_service, user_service

from pytz import utc

from utils import cfg

executors = {
    'default': ThreadPoolExecutor(20)
}

job_defaults = {
    # 'coalesce': True
}

BOT_GLOBAL = None


class Tasks():
    """Job scheduler for unmute, using APScheduler"""

    def __init__(self, bot: discord.Client):
        """Initialize scheduler

        Parameters
        ----------
        bot : discord.Client
            instance of Discord client

        """

        global BOT_GLOBAL
        BOT_GLOBAL = bot

        # logging.basicConfig()
        # logging.getLogger('apscheduler').setLevel(logging.DEBUG)

        if os.environ.get("DB_CONNECTION_STRING") is None:
            jobstores = {
                'default': MongoDBJobStore(database="botty", collection="jobs", host=os.environ.get("DB_HOST"), port=int(os.environ.get("DB_PORT"))),
            }
        else:
            jobstores = {
                'default': MongoDBJobStore(database="botty", collection="jobs", host=os.environ.get("DB_CONNECTION_STRING")),
            }

        self.tasks = AsyncIOScheduler(
            jobstores=jobstores, executors=executors, job_defaults=job_defaults, event_loop=bot.loop, timezone=utc)
        self.tasks.start()

    def schedule_untimeout(self, id: int, date: datetime) -> None:
        """Create a task to unmute user given by ID `id`, at time `date`

        Parameters
        ----------
        id : int
            User to unmute
        date : datetime.datetime
            When to unmute

        """

        self.tasks.add_job(untimeout_callback, 'date', id=str(
            id), next_run_time=date, args=[id], misfire_grace_time=3600)

    def schedule_remove_bday(self, id: int, date: datetime) -> None:
        """Create a task to remove birthday role from user given by ID `id`, at time `date`

        Parameters
        ----------
        id : int
            User to remove role
        date : datetime.datetime
            When to remove role

        """

        self.tasks.add_job(remove_bday_callback, 'date', id=str(
            id+1), next_run_time=date, args=[id], misfire_grace_time=3600)

    def cancel_unmute(self, id: int) -> None:
        """When we manually unmute a user given by ID `id`, stop the task to unmute them.

        Parameters
        ----------
        id : int
            User whose unmute task we want to cancel

        """

        self.tasks.remove_job(str(id), 'default')

    def cancel_unmute(self, id: int) -> None:
        """When we manually unmute a user given by ID `id`, stop the task to unmute them.

        Parameters
        ----------
        id : int
            User whose unmute task we want to cancel

        """

        self.tasks.remove_job(str(id), 'default')

    def cancel_unbirthday(self, id: int) -> None:
        """When we manually unset the birthday of a user given by ID `id`, stop the task to remove the role.

        Parameters
        ----------
        id : int
            User whose task we want to cancel

        """
        self.tasks.remove_job(str(id+1), 'default')

    def schedule_end_giveaway(self, channel_id: int, message_id: int, date: datetime, winners: int) -> None:
        """
        Create a task to end a giveaway with message ID `id`, at date `date`

        Parameters
        ----------
        channel_id : int
            ID of the channel that the giveaway is in
        message_id : int
            Giveaway message ID
        date : datetime.datetime
            When to end the giveaway

        """

        self.tasks.add_job(end_giveaway_callback, 'date', id=str(
            message_id+2), next_run_time=date, args=[channel_id, message_id, winners], misfire_grace_time=3600)

    def schedule_reminder(self, id: int, reminder: str, date: datetime) -> None:
        """Create a task to remind someone of id `id` of something `reminder` at time `date`

        Parameters
        ----------
        id : int
            User to remind
        reminder : str
            What to remind them of
        date : datetime.datetime
            When to remind

        """

        self.tasks.add_job(reminder_callback, 'date', id=str(
            id+random.randint(5, 100)), next_run_time=date, args=[id, reminder], misfire_grace_time=3600)


def untimeout_callback(id: int) -> None:
    """Callback function for actually unmuting. Creates asyncio task
    to do the actual unmute.

    Parameters
    ----------
    id : int
        User who we want to unmute

    """

    BOT_GLOBAL.loop.create_task(remove_timeout(id))


async def remove_timeout(id: int) -> None:
    """Remove the mute role of the user given by ID `id`

    Parameters
    ----------
    id : int
        User to unmute

    """

    case = Case(
        _id=await guild_service.get_new_case_id(),
        _type="UNMUTE",
        mod_id=BOT_GLOBAL.user.id,
        mod_tag=str(BOT_GLOBAL.user),
        reason="Temporary mute expired.",
    )
    await guild_service.inc_case_id()
    user_service.add_case(id, case)

    guild = BOT_GLOBAL.get_guild(cfg.guild_id)
    user: discord.Member = guild.get_member(id)
    if user is None:
        return

    await user.edit(timed_out_until=None)

    # i know. this sucks.
    from utils.mod import prepare_unmute_log
    log = prepare_unmute_log(BOT_GLOBAL.user, user, case)
    log.remove_author()
    log.set_thumbnail(url=user.display_avatar)

    public_chan = guild.get_channel(
        (await guild_service.get_channels()).channel_public)

    dmed = True
    try:
        await user.send(embed=log)
    except Exception:
        dmed = False

    await public_chan.send(user.mention if not dmed else "", embed=log)


def reminder_callback(id: int, reminder: str):
    BOT_GLOBAL.loop.create_task(remind(id, reminder))


async def remind(id, reminder):
    """Remind the user callback

    Parameters
    ----------
    id : int
        ID of user to remind
    reminder : str
        body of reminder

    """

    guild = BOT_GLOBAL.get_guild(cfg.guild_id)
    if guild is None:
        return
    member = guild.get_member(id)
    if member is None:
        return

    embed = discord.Embed(
        title="Reminder!", description=f"*You wanted me to remind you something... What was it... Oh right*:\n\n{reminder}", color=discord.Color.random())
    try:
        await member.send(embed=embed)
    except Exception:
        channel = guild.get_channel(
            (await guild_service.get_channels()).channel_botspam)
        await channel.send(member.mention, embed=embed)


def remove_bday_callback(id: int) -> None:
    """Callback function for actually unmuting. Creates asyncio task
    to do the actual unmute.

    Parameters
    ----------
    id : int
        User who we want to unmute

    """

    BOT_GLOBAL.loop.create_task(remove_bday(id))


async def remove_bday(id: int) -> None:
    """Remove the bday role of the user given by ID `id`

    Parameters
    ----------
    id : int
        User to remove role of

    """

    db_guild = await guild_service.get_roles()
    guild = BOT_GLOBAL.get_guild(cfg.guild_id)
    if guild is None:
        return

    bday_role = db_guild.role_birthday
    bday_role = guild.get_role(bday_role)
    if bday_role is None:
        return

    user = guild.get_member(id)
    await user.remove_roles(bday_role)


def end_giveaway_callback(channel_id: int, message_id: int, winners: int) -> None:
    """
    Callback function for ending a giveaway

    Parameters
    ----------
    channel_id : int
        ID of the channel that the giveaway is in
    message_id : int
        Message ID of the giveaway

    """

    BOT_GLOBAL.loop.create_task(end_giveaway(channel_id, message_id, winners))


async def end_giveaway(channel_id: int, message_id: int, winners: int) -> None:
    """
    End a giveaway.

    Parameters
    ----------
    channel_id : int
        ID of the channel that the giveaway is in
    message_id : int
        Message ID of the giveaway

    """

    guild = BOT_GLOBAL.get_guild(cfg.guild_id)
    channel = guild.get_channel(channel_id)

    if channel is None:
        return
    try:
        message = await channel.fetch_message(message_id)
    except Exception:
        return

    embed = message.embeds[0]
    embed.set_footer(text="Ended")
    embed.set_field_at(0, name="Time remaining",
                       value="This giveaway has ended.")
    embed.timestamp = datetime.now()
    embed.color = discord.Color.default()

    reaction = message.reactions[0]
    reacted_ids = [user.id async for user in reaction.users()]
    reacted_ids.remove(BOT_GLOBAL.user.id)

    if len(reacted_ids) < winners:
        winners = len(reacted_ids)

    rand_ids = random.sample(reacted_ids, winners)
    winner_ids = []
    mentions = []
    tries = 0
    for user_id in rand_ids:
        tries += 1
        member = guild.get_member(user_id)
        # ensure that member hasn't left the server while simultaneously ensuring that we don't add duplicate members if we select a new random one
        while member is None or member.mention in mentions:
            tries += 1
            if tries > winners + 20:
                member = None
                break
            member = guild.get_member(random.choice(reacted_ids))
        if member is not None:
            mentions.append(member.mention)
            winner_ids.append(member.id)

    g = guild_service.get_giveaway(_id=message.id)
    g.entries = reacted_ids
    g.is_ended = True
    g.previous_winners = winner_ids
    g.save()

    await message.edit(embed=embed)
    await message.clear_reactions()

    if not mentions:
        await channel.send(f"No winner was selected for the giveaway of **{g.name}** because nobody entered.")
        return

    if winners == 1:
        await channel.send(f"Congratulations {mentions[0]}! You won the giveaway of **{g.name}**! Please DM or contact <@{g.sponsor}> to collect.")
    else:
        await channel.send(f"Congratulations {', '.join(mentions)}! You won the giveaway of **{g.name}**! Please DM or contact <@{g.sponsor}> to collect.")