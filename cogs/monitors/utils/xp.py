import datetime
import discord
from discord.ext import commands

from random import randint
from data.services.user_service import user_service
from data.services.xp_service import award_xp, level_for_xp
from utils.config import cfg


class Xp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        if member.guild.id != cfg.guild_id:
            return

        user = await user_service.get_user(id=member.id)

        if user.is_xp_frozen or user.is_clem:
            return

        level = user.level

        roles_to_add = await self.assess_new_roles(level, member)
        await self.add_new_roles(member, roles_to_add)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if message.guild.id != cfg.guild_id:
            return
        if message.author.bot:
            return

        if message.channel.id == cfg.channels.bot_commands:
            return

        xp_to_add = randint(0, 11)
        result = await self.bot.database_io.run(award_xp, message.author.id, xp_to_add)
        if result is None:
            return
        roles_to_add = await self.assess_new_roles(result.level, message.author)
        await self.add_new_roles(message, roles_to_add)

    async def assess_new_roles(self, new_level, member: discord.Member):
        roles_to_add = []
        if 15 > new_level and cfg.roles.new_member is not None:
            member_joined_less_than_a_day_ago = datetime.datetime.now(datetime.timezone.utc) - member.created_at < datetime.timedelta(days=1)
            if member_joined_less_than_a_day_ago:
                roles_to_add.append(cfg.roles.new_member)
                await self.bot.tasks.schedule_remove_new_member_role(
                    member.id, member.created_at + datetime.timedelta(days=1))
        if 15 <= new_level:
            roles_to_add.append(cfg.roles.member_plus)
        if 30 <= new_level:
            roles_to_add.append(cfg.roles.member_pro)
        if 50 <= new_level:
            roles_to_add.append(cfg.roles.member_edition)
        if 75 <= new_level:
            roles_to_add.append(cfg.roles.member_one)
        if 100 <= new_level:
            roles_to_add.append(cfg.roles.member_ultra)

        return roles_to_add

    async def add_new_roles(self, obj, roles_to_add):
        if roles_to_add is None:
            return

        member = obj
        if isinstance(obj, discord.Message):
            member = obj.author

        roles_to_add = [member.guild.get_role(role) for role in roles_to_add if member.guild.get_role(
            role) is not None and member.guild.get_role(role) not in member.roles]
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason="XP roles")

    def get_level(self, current_xp):
        return level_for_xp(current_xp)


class StickyRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id != cfg.guild_id:
            return

        roles = [role.id for role in member.roles if role <
                 member.guild.me.top_role and role != member.guild.default_role]
        await user_service.set_sticky_roles(member.id, roles)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != cfg.guild_id:
            return

        possible_roles = (await user_service.get_user(member.id)).sticky_roles
        roles = [member.guild.get_role(role) for role in possible_roles if member.guild.get_role(
            role) is not None and member.guild.get_role(role) < member.guild.me.top_role]
        await member.add_roles(*roles, reason="Sticky roles")


async def setup(bot):
    await bot.add_cog(StickyRoles(bot))
    await bot.add_cog(Xp(bot))
