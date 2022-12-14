import re
from asyncio import Lock
from datetime import datetime, timedelta, timezone

import discord
from data.model import Case
from data.services import guild_service, user_service
from discord.ext import commands
from expiringdict import ExpiringDict
from utils import cfg
from utils.framework import MessageTextBucket, gatekeeper, find_triggered_raid_phrases
from utils.mod import mute, prepare_ban_log
from utils.views import report_raid, report_raid_phrase, report_spam


class RaidType:
    PingSpam = 1
    RaidPhrase = 2
    MessageSpam = 3
    JoinSpamOverTime = 4
    RaidPhraseDetection = 5


class AntiRaidMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # cooldown to monitor if too many users join in a short period of time (more than 10 within 8 seconds)
        self.join_raid_detection_threshold = commands.CooldownMapping.from_cooldown(
            rate=10, per=8, type=commands.BucketType.guild)
        # cooldown to monitor if users are spamming a message (8 within 6 seconds)
        self.message_spam_detection_threshold = commands.CooldownMapping.from_cooldown(
            rate=7, per=6.0, type=commands.BucketType.member)
        # cooldown to monitor if too many accounts created on the same date are joining within a short period of time
        # (5 accounts created on the same date joining within 45 minutes of each other)
        self.join_overtime_raid_detection_threshold = commands.CooldownMapping.from_cooldown(
            rate=4, per=2700, type=MessageTextBucket.custom)

        # cooldown to monitor how many times AntiRaid has been triggered (5 triggers per 15 seconds puts server in lockdown)
        self.raid_detection_threshold = commands.CooldownMapping.from_cooldown(
            rate=4, per=15.0, type=commands.BucketType.guild)
        # cooldown to only send one raid alert for moderators per 10 minutes
        self.raid_alert_cooldown = commands.CooldownMapping.from_cooldown(
            1, 600.0, commands.BucketType.guild)
        # cooldown to only send one report per spamming member
        self.spam_report_cooldown = commands.CooldownMapping.from_cooldown(
            rate=1, per=10.0, type=commands.BucketType.member)

        # stores the users that trigger self.join_raid_detection_threshold so we can ban them
        self.join_user_mapping = ExpiringDict(max_len=100, max_age_seconds=10)
        # stores the users that trigger self.message_spam_detection_threshold so we can ban them
        self.spam_user_mapping = ExpiringDict(max_len=100, max_age_seconds=10)
        # stores the users that trigger self.join_overtime_raid_detection_threshold so we can ban them
        self.join_overtime_mapping = ExpiringDict(
            max_len=100, max_age_seconds=2700)
        # stores the users that we have banned so we don't try to ban them repeatedly
        self.ban_user_mapping = ExpiringDict(max_len=100, max_age_seconds=120)

        # locks to prevent race conditions when banning concurrently
        self.join_overtime_lock = Lock()
        self.banning_lock = Lock()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Antiraid filter for when members join.
        This watches for when too many members join within a small period of time,
        as well as when too many users created on the same day join within a small period of time

        Parameters
        ----------
        member : discord.Member
            the member that joined
        """

        if member.guild.id != cfg.guild_id:
            return
        if member.bot:
            return

        """Detect whether more than 10 users join within 8 seconds"""
        # add user to cooldown
        current = datetime.now().timestamp()
        join_spam_detection_bucket = self.join_raid_detection_threshold.get_bucket(
            member)
        self.join_user_mapping[member.id] = member

        # if ratelimit is triggered, we should ban all the users that joined in the past 8 seconds
        if join_spam_detection_bucket.update_rate_limit(current):
            users = list(self.join_user_mapping.keys())
            for user in users:
                try:
                    user = self.join_user_mapping[user]
                except KeyError:
                    continue

                try:
                    await self.raid_ban(user, reason="Join spam detected.")
                except Exception:
                    pass

            raid_alert_bucket = self.raid_alert_cooldown.get_bucket(member)
            if not raid_alert_bucket.update_rate_limit(current):
                await report_raid(member)
                await self.freeze_server(member.guild)

        """Detect whether more than 4 users created on the same day
        (after May 1st 2021) join within 45 minutes of each other"""

        # skip if the user was created within the last 15 minutes
        if member.created_at > datetime.now(member.created_at.tzinfo) - timedelta(minutes=15):
            return

        # skip user if we manually verified them, i.e they were approved by a moderator
        # using the !verify command when they appealed a ban.
        if user_service.get_user(member.id).raid_verified:
            return

        # skip if it's an older account (before May 1st 2021)
        if member.created_at < datetime.strptime("01/05/21 00:00:00", '%d/%m/%y %H:%M:%S').replace(tzinfo=member.created_at.tzinfo):
            return

        # this setting disables the filter for accounts created from "Today"
        # useful when we get alot of new users, for example when a new Jailbreak is released.
        # this setting is controlled using !spammode
        if not (await guild_service.get_meta_properties()).ban_today_spam_accounts:
            now = datetime.today()
            now = [now.year, now.month, now.day]
            member_now = [member.created_at.year,
                          member.created_at.month, member.created_at.day]

            if now == member_now:
                return

        timestamp_bucket_for_logging = member.created_at.strftime(
            "%B %d, %Y, %I %p")
        # generate string representation for the account creation date (July 1st, 2021 for example).
        # we will use this for the cooldown mechanism, to ratelimit accounts created on this date.
        timestamp = member.created_at.strftime(
            "%B %d, %Y")

        # store this user with all the users that were created on this date
        async with self.join_overtime_lock:
            if self.join_overtime_mapping.get(timestamp) is None:
                self.join_overtime_mapping[timestamp] = [member]
            else:
                if member in self.join_overtime_mapping[timestamp]:
                    return

                self.join_overtime_mapping[timestamp].append(member)

        # handle ratelimitting. If ratelimit is triggered, ban all the users we know were created on this date.
        bucket = self.join_overtime_raid_detection_threshold.get_bucket(
            timestamp)
        current = member.joined_at.replace(tzinfo=timezone.utc).timestamp()
        if bucket.update_rate_limit(current):
            users = [m for m in self.join_overtime_mapping.get(timestamp)]
            for user in users:
                try:
                    await self.raid_ban(user, reason=f"Join spam over time detected (bucket `{timestamp_bucket_for_logging}`)", dm_user=True)
                    self.join_overtime_mapping[timestamp].remove(user)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return
        if message.author.bot:
            return
        if message.guild.id != cfg.guild_id:
            return
        message.author = message.guild.get_member(message.author.id)
        if gatekeeper.has(message.guild, message.author, 5):
            return

        if await self.ping_spam(message):
            await self.handle_raid_detection(message, RaidType.PingSpam)
        elif await self.raid_phrase_detected(message):
            await self.handle_raid_detection(message, RaidType.RaidPhrase)
        elif await self.message_spam(message):
            await self.handle_raid_detection(message, RaidType.MessageSpam)
        elif await self.detect_scam_link(message):
            await self.report_possible_raid_phrase(message)

    async def detect_scam_link(self, message: discord.Message):
        # check if message contains @everyone or @here
        if ("@everyone" not in message.content and "@here" not in message.content) and \
                ("take it" not in message.content and "airdrop" not in message.content and "nitro" not in message.content):
            return False

        # use regex to find if message contains url
        url = re.search(r'(https?://\S+)', message.content)
        if url is None:
            return False

        # don't trigger if this user isn't a whitename
        if gatekeeper.has(message.guild, message.author, 1):
            return False

        # don't spam this
        bucket = self.spam_report_cooldown.get_bucket(message)
        current = message.created_at.replace(tzinfo=timezone.utc).timestamp()
        if bucket.update_rate_limit(current):
            return False

        return True

    async def handle_raid_detection(self, message: discord.Message, raid_type: RaidType):
        current = message.created_at.replace(tzinfo=timezone.utc).timestamp()
        spam_detection_bucket = self.raid_detection_threshold.get_bucket(
            message)
        user = message.author

        do_freeze = False
        do_banning = False
        self.spam_user_mapping[user.id] = 1

        # has the antiraid filter been triggered 5 or more times in the past 10 seconds?
        if spam_detection_bucket.update_rate_limit(current):
            do_banning = True
            # yes! notify the mods and lock the server.
            raid_alert_bucket = self.raid_alert_cooldown.get_bucket(message)
            if not raid_alert_bucket.update_rate_limit(current):
                await report_raid(user, message)
                do_freeze = True

        # lock the server
        if do_freeze:
            await self.freeze_server(message.guild)

        # ban all the spammers
        if raid_type in [RaidType.PingSpam, RaidType.MessageSpam]:
            if not do_banning and not do_freeze:
                if raid_type is RaidType.PingSpam:
                    title = "Ping spam detected"
                else:
                    title = "Message spam detected"
                await report_spam(self.bot, message, user, title=title)
            else:
                users = list(self.spam_user_mapping.keys())
                for user in users:
                    try:
                        _ = self.spam_user_mapping[user]
                    except KeyError:
                        continue

                    user = message.guild.get_member(user)
                    if user is None:
                        continue

                    try:
                        await self.raid_ban(user, reason="Ping spam detected" if raid_type is RaidType.PingSpam else "Message spam detected")
                    except Exception:
                        pass

    async def ping_spam(self, message):
        """If a user pings more than 5 people, or pings more than 2 roles, mute them.
        A report is generated which a mod must review (either unmute or ban the user using a react)
        """

        if len(set(message.mentions)) > 4 or len(set(message.role_mentions)) > 2:
            bucket = self.spam_report_cooldown.get_bucket(message)
            current = message.created_at.replace(
                tzinfo=timezone.utc).timestamp()
            if not bucket.update_rate_limit(current):
                user = message.author
                ctx = await self.bot.get_context(message)
                await mute(ctx, user, mod=ctx.guild.me, reason="Ping spam")
                return True

        return False

    async def message_spam(self, message):
        """If a message is spammed 8 times in 5 seconds, mute the user and generate a report.
        A mod must either unmute or ban the user.
        """

        if gatekeeper.has(message.guild, message.author, 1):
            return False

        bucket = self.message_spam_detection_threshold.get_bucket(message)
        current = message.created_at.replace(tzinfo=timezone.utc).timestamp()

        if bucket.update_rate_limit(current):
            bucket = self.spam_report_cooldown.get_bucket(message)
            current = message.created_at.replace(
                tzinfo=timezone.utc).timestamp()
            if not bucket.update_rate_limit(current):
                user = message.author
                ctx = await self.bot.get_context(message)
                await mute(ctx, user, mod=ctx.guild.me, reason="Message spam")
                return True

        return False

    async def raid_phrase_detected(self, message):
        """Raid phrases are specific phrases (such as known scam URLs), and upon saying them, whitenames
        will immediately be banned. Uses the same system as filters to search messages for the phrases.
        """

        if gatekeeper.has(message.guild, message.author, 2):
            return False

        if await find_triggered_raid_phrases(message.content, message.author) is not None:
            await self.raid_ban(message.author)
            return True

        return False

    async def report_possible_raid_phrase(self, message):
        # use regex to find url from message
        url = re.search(r'(https?://\S+)', message.content)

        # extract domain from url
        domain = url.group(1).split("/")[2]
        if domain == "discord.gg":
            return

        if domain in ["bit.ly", "github.com"]:
            # for bit.ly we don't want to ban the whole domain, just this specific one
            domain = url.group(1)

        ctx = await self.bot.get_context(message)
        user = message.author
        await mute(ctx, user, mod=ctx.guild.me, reason="Possible new raid phrase detected")

        # report the user to mods
        await report_raid_phrase(self.bot, message, domain)

        # delete the message so nobody (accidentally) opens it
        await ctx.guild.message.delete()

    async def raid_ban(self, user: discord.Member, reason="Raid phrase detected", dm_user=False):
        """Helper function to ban users"""

        async with self.banning_lock:
            # if self.ban_user_mapping.get(user.id) is not None:
            if self.bot.ban_cache.is_banned(user.id):
                return
            else:
                self.bot.ban_cache.ban(user.id)

            case = Case(
                _id=await guild_service.get_new_case_id(),
                _type="BAN",
                date=datetime.now(),
                mod_id=self.bot.user.id,
                mod_tag=str(self.bot.user),
                punishment="PERMANENT",
                reason=reason
            )

            await guild_service.inc_case_id()
            user_service.add_case(user.id, case)

            log = prepare_ban_log(self.bot.user, user, case)

            if dm_user:
                try:
                    await user.send(f"You were banned from {user.guild.name}.\n\nThis action was performed automatically. If you think this was a mistake, please send a message here: https://www.reddit.com/message/compose?to=%2Fr%2FJailbreak", embed=log)
                except Exception:
                    pass

            if user.guild.get_member(user.id) is not None:
                await user.ban(reason="Raid")
            else:
                await user.guild.ban(discord.Object(id=user.id), reason="Raid")

            public_logs = user.guild.get_channel((await guild_service.get_channels()).channel_public)
            if public_logs:
                log.remove_author()
                log.set_thumbnail(url=user.display_avatar)
                await public_logs.send(embed=log)

    async def freeze_server(self, guild):
        """Freeze all channels marked as freezeable during a raid, meaning only people with the Member+ role and up
        can talk (temporarily lock out whitenames during a raid)"""

        db_guild = await guild_service.get_meta_properties()
        for channel in db_guild.locked_channels:
            channel = guild.get_channel(channel)
            if channel is None:
                continue

            default_role = guild.default_role
            member_plus = guild.get_role((await guild_service.get_roles()).role_memberplus)

            default_perms = channel.overwrites_for(default_role)
            memberplus_perms = channel.overwrites_for(member_plus)

            if default_perms.send_messages is None and memberplus_perms.send_messages is None:
                default_perms.send_messages = False
                memberplus_perms.send_messages = True

                try:
                    await channel.set_permissions(default_role, overwrite=default_perms, reason="Locked!")
                    await channel.set_permissions(member_plus, overwrite=memberplus_perms, reason="Locked!")
                except Exception:
                    pass


async def setup(bot):
    await bot.add_cog(AntiRaidMonitor(bot))
