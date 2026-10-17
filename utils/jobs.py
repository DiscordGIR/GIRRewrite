from data.database import run_database
import asyncio
import os
import threading
from functools import wraps
import random
from uuid import uuid4
from datetime import datetime, timedelta, timezone

import discord
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from data.model import Case
from data.services import guild_service, user_service

from pytz import utc

from utils import cfg

job_defaults = {
    # 'coalesce': True
}

BOT_GLOBAL = None


class _Scheduler:
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
                'default': MongoDBJobStore(database="botty", collection="jobs", host=os.environ.get("DB_HOST"), port=int(os.environ.get("DB_PORT")), serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=10000),
            }
        else:
            jobstores = {
                'default': MongoDBJobStore(database="botty", collection="jobs", host=os.environ.get("DB_CONNECTION_STRING"), serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=10000),
            }

        self.tasks = AsyncIOScheduler(
            jobstores=jobstores, executors={"default": AsyncIOExecutor()}, job_defaults=job_defaults, event_loop=asyncio.get_running_loop(), timezone=utc)
        self.tasks.start(paused=True)

    def schedule_untimeout(self, _id: int, date: datetime) -> None:
        """Create a task to unmute user given by ID `_id`, at time `date`

        Parameters
        ----------
        _id : int
            User to unmute
        date : datetime.datetime
            When to unmute

        """

        self._remove_legacy_job(_id, untimeout_callback)
        self.tasks.add_job(untimeout_callback, 'date', id=f"timeout:{_id}",
                           next_run_time=date, args=[_id], replace_existing=True,
                           misfire_grace_time=3600)

    def schedule_remove_bday(self, _id: int, date: datetime) -> None:
        """Create a task to remove birthday role from user given by ID `_id`, at time `date`

        Parameters
        ----------
        _id : int
            User to remove role
        date : datetime.datetime
            When to remove role

        """

        self._remove_legacy_job(_id + 1, remove_bday_callback)
        self.tasks.add_job(remove_bday_callback, 'date', id=f"birthday:{_id}",
                           next_run_time=date, args=[_id], replace_existing=True,
                           misfire_grace_time=3600)

    def _remove_job(self, job_id):
        try:
            self.tasks.remove_job(job_id)
        except JobLookupError:
            pass

    def _remove_legacy_job(self, job_id, callback):
        # Numeric IDs are retained in deployed databases. Never remove a job
        # belonging to a different feature just because its numeric ID collides.
        job = self.tasks.get_job(str(job_id))
        if job is not None and job.func == callback:
            self._remove_job(str(job_id))

    def cancel_unmute(self, member_id: int) -> None:
        self._remove_job(f"timeout:{member_id}")
        self._remove_legacy_job(member_id, untimeout_callback)

    def cancel_unbirthday(self, _id: int) -> None:
        """When we manually unset the birthday of a user given by ID `_id`, stop the task to remove the role.

        Parameters
        ----------
        _id : int
            User whose task we want to cancel

        """
        self._remove_job(f"birthday:{_id}")
        self._remove_legacy_job(_id + 1, remove_bday_callback)

    def schedule_end_giveaway(self, channel_id: int, message_id: int, date: datetime, winners: int) -> None:
        """
        Create a task to end a giveaway with message ID `_id`, at date `date`

        Parameters
        ----------
        channel_id : int
            ID of the channel that the giveaway is in
        message_id : int
            Giveaway message ID
        date : datetime.datetime
            When to end the giveaway

        """

        self._remove_legacy_job(message_id + 2, end_giveaway_callback)
        self.tasks.add_job(end_giveaway_callback, 'date', id=f"giveaway:{message_id}",
                           next_run_time=date, args=[channel_id, message_id, winners],
                           replace_existing=True, misfire_grace_time=3600)

    def schedule_reminder(self, _id: int, reminder: str, date: datetime) -> None:
        """Create a task to remind someone of id `_id` of something `reminder` at time `date`

        Parameters
        ----------
        _id : int
            User to remind
        reminder : str
            What to remind them of
        date : datetime.datetime
            When to remind

        """

        self.tasks.add_job(reminder_callback, 'date', id=f"reminder:{_id}:{uuid4().hex}",
                           next_run_time=date, args=[_id, reminder], misfire_grace_time=3600)

    def schedule_remove_new_member_role(self, member_id: int, date=None) -> None:
        """Create a task to remove new member role from user given by ID `_id`, at time `date`

        Parameters
        ----------
        _id : int
            User to remove role
        date : datetime.datetime
            When to remove role

        """

        job_id = f"new-member:{member_id}"
        if self.tasks.get_job(job_id) is not None:
            return
        # Collapse legacy randomly named jobs for this member, keeping the
        # earliest deadline rather than postponing removal on every message.
        legacy = [job for job in self.tasks.get_jobs()
                  if job.func == remove_new_member_role_callback
                  and job.args == (member_id,)]
        deadline = date or datetime.now(timezone.utc) + timedelta(days=1)
        if legacy:
            deadline = min([deadline] + [job.next_run_time for job in legacy])
        self.tasks.add_job(remove_new_member_role_callback, 'date', id=job_id,
                           next_run_time=deadline, args=[member_id], misfire_grace_time=3600)
        for job in legacy:
            self._remove_job(job.id)

    def cancel_giveaway(self, message_id):
        self._remove_job(f"giveaway:{message_id}")
        self._remove_legacy_job(message_id + 2, end_giveaway_callback)

    def resume(self):
        if self.tasks.running:
            self.tasks.resume()

    def close(self):
        if self.tasks.running:
            self.tasks.shutdown(wait=False)


def scheduler_method(name):
    async def invoke(self, *args, **kwargs):
        return await self._call(getattr(self._scheduler, name), *args, **kwargs)
    return invoke


class Tasks:
    """Own the scheduler's blocking job store on a dedicated event-loop thread.

    Only scheduling runs there. Persisted callbacks dispatch Discord work back
    to the bot loop; their original module/function references remain valid.
    """
    def __init__(self, bot):
        self.bot = bot
        self._loop = None
        self._thread = None
        self._scheduler = None
        self._slots = asyncio.Semaphore(1)
        self._closed = False
        self._running_callbacks = set()

    @property
    def tasks(self):
        # Read-only diagnostic access. Use the awaitable methods for mutations.
        return self._scheduler.tasks

    async def start(self):
        if self._thread is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever,
                                        name="gir-scheduler", daemon=True)
        self._thread.start()
        def initialize():
            self._scheduler = _Scheduler(self.bot)

        try:
            await self._call(initialize)
        except BaseException:
            await self.close()
            raise

    async def _call(self, function, *args, **kwargs):
        if self._closed:
            raise RuntimeError("Scheduler is closed")
        await self._slots.acquire()
        if self._closed:
            self._slots.release()
            raise RuntimeError("Scheduler is closed")

        async def invoke():
            return function(*args, **kwargs)

        try:
            future = asyncio.wrap_future(asyncio.run_coroutine_threadsafe(invoke(), self._loop))
        except BaseException:
            self._slots.release()
            raise

        def finished(result):
            self._slots.release()
            if not result.cancelled():
                result.exception()

        future.add_done_callback(finished)
        return await asyncio.shield(future)

    schedule_untimeout = scheduler_method("schedule_untimeout")
    schedule_remove_bday = scheduler_method("schedule_remove_bday")
    cancel_unmute = scheduler_method("cancel_unmute")
    cancel_unbirthday = scheduler_method("cancel_unbirthday")
    schedule_end_giveaway = scheduler_method("schedule_end_giveaway")
    cancel_giveaway = scheduler_method("cancel_giveaway")
    schedule_reminder = scheduler_method("schedule_reminder")
    schedule_remove_new_member_role = scheduler_method("schedule_remove_new_member_role")
    resume = scheduler_method("resume")

    async def close(self):
        if self._closed:
            return
        self._closed = True
        if self._loop is None:
            return
        # Drain already accepted mutations before closing the store.
        async with self._slots:
            async def shutdown():
                if self._scheduler is not None:
                    self._scheduler.close()
                    await asyncio.sleep(0)  # AsyncIOScheduler.shutdown is queued.
                pending = [task for task in asyncio.all_tasks()
                           if task is not asyncio.current_task()]
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

            await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(shutdown(), self._loop))
            # Wait for cancellation of the actual Discord coroutines as well as
            # their cross-thread proxy futures before closing database/HTTP pools.
            pending = list(self._running_callbacks)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            self._loop.call_soon_threadsafe(self._loop.stop)
            await asyncio.to_thread(self._thread.join)
            self._loop.close()


def on_bot_loop(function):
    @wraps(function)
    async def dispatch(*args, **kwargs):
        if asyncio.get_running_loop() is BOT_GLOBAL.loop:
            return await function(*args, **kwargs)

        async def execute():
            owner = BOT_GLOBAL.tasks
            if owner._closed:
                return
            task = asyncio.current_task()
            owner._running_callbacks.add(task)
            try:
                return await function(*args, **kwargs)
            finally:
                owner._running_callbacks.discard(task)

        future = asyncio.run_coroutine_threadsafe(execute(), BOT_GLOBAL.loop)
        return await asyncio.wrap_future(future)
    return dispatch


@on_bot_loop
async def untimeout_callback(_id: int) -> None:
    """Callback function for actually unmuting. Creates asyncio task
    to do the actual unmute.

    Parameters
    ----------
    _id : int
        User who we want to unmute

    """

    await remove_timeout(_id)


async def remove_timeout(_id: int) -> None:
    """Remove the mute role of the user given by ID `_id`

    Parameters
    ----------
    _id : int
        User to unmute

    """

    guild = BOT_GLOBAL.get_guild(cfg.guild_id)
    if guild is None:
        return
    user = guild.get_member(_id)
    if user is None or user.is_timed_out():
        # Discord expires timeouts itself. An old job must never clear a newer
        # punishment, including one issued outside this bot.
        return

    case = Case(
        _id=await guild_service.allocate_case_id(),
        _type="UNMUTE",
        mod_id=BOT_GLOBAL.user.id,
        mod_tag=str(BOT_GLOBAL.user),
        reason="Temporary mute expired.",
    )
    await user_service.add_case(_id, case)

    # i know. this sucks.
    from utils.mod import prepare_unmute_log
    log = prepare_unmute_log(BOT_GLOBAL.user, user, case)
    log.remove_author()
    log.set_thumbnail(url=user.display_avatar)

    public_chan = guild.get_channel(cfg.channels.public_logs)

    dmed = True
    try:
        await user.send(embed=log)
    except Exception:
        dmed = False

    await public_chan.send(user.mention if not dmed else "", embed=log)


@on_bot_loop
async def reminder_callback(id: int, reminder: str):
    await remind(id, reminder)


async def remind(_id, reminder):
    """Remind the user callback

    Parameters
    ----------
    _id : int
        ID of user to remind
    reminder : str
        body of reminder

    """

    guild = BOT_GLOBAL.get_guild(cfg.guild_id)
    if guild is None:
        return
    member = guild.get_member(_id)
    if member is None:
        return

    embed = discord.Embed(
        title="Reminder!", description=f"*You wanted me to remind you something... What was it... Oh right*:\n\n{reminder}", color=discord.Color.random())
    try:
        await member.send(embed=embed)
    except Exception:
        channel = guild.get_channel(cfg.channels.bot_commands)
        await channel.send(member.mention, embed=embed)


@on_bot_loop
async def remove_bday_callback(_id: int) -> None:
    """Callback function for actually unmuting. Creates asyncio task
    to do the actual unmute.

    Parameters
    ----------
    _id : int
        User who we want to unmute

    """

    await remove_bday(_id)


async def remove_bday(_id: int) -> None:
    """Remove the bday role of the user given by ID `_id`

    Parameters
    ----------
    _id : int
        User to remove role of

    """

    guild = BOT_GLOBAL.get_guild(cfg.guild_id)
    if guild is None:
        return

    bday_role = cfg.roles.birthday
    bday_role = guild.get_role(bday_role)
    if bday_role is None:
        return

    user = guild.get_member(_id)
    if user is not None:
        await user.remove_roles(bday_role)


@on_bot_loop
async def end_giveaway_callback(channel_id: int, message_id: int, winners: int) -> None:
    """
    Callback function for ending a giveaway

    Parameters
    ----------
    channel_id : int
        ID of the channel that the giveaway is in
    message_id : int
        Message ID of the giveaway

    """

    await end_giveaway(channel_id, message_id, winners)


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

    g = await guild_service.get_giveaway(_id=message.id)
    g.entries = reacted_ids
    g.is_ended = True
    g.previous_winners = winner_ids
    await run_database(lambda: g.save())

    await message.edit(embed=embed)
    await message.clear_reactions()

    if not mentions:
        await channel.send(f"No winner was selected for the giveaway of **{g.name}** because nobody entered.")
        return

    if winners == 1:
        await channel.send(f"Congratulations {mentions[0]}! You won the giveaway of **{g.name}**! Please DM or contact <@{g.sponsor}> to collect.")
    else:
        await channel.send(f"Congratulations {', '.join(mentions)}! You won the giveaway of **{g.name}**! Please DM or contact <@{g.sponsor}> to collect.")

@on_bot_loop
async def remove_new_member_role_callback(member_id: int) -> None:
    """Callback function for actually removing new member role. Creates asyncio task
    to do the actual removal.

    Parameters
    ----------
    _id : int
        User who we want to remove the role from

    """

    await remove_new_member_role(member_id)

async def remove_new_member_role(member_id: int) -> None:
    """Remove the new member role of the user given by ID `_id`

    Parameters
    ----------
    role : int
        Role to remove
    member_id : int
        User to remove role of

    """

    guild = BOT_GLOBAL.get_guild(cfg.guild_id)
    if guild is None:
        return

    new_member_role = cfg.roles.new_member
    new_member_role = guild.get_role(new_member_role)
    if new_member_role is None:
        return

    user = guild.get_member(member_id)
    if user is not None:
        await user.remove_roles(new_member_role)
