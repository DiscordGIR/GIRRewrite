import discord
from discord.ext import commands

import math
from random import randint
from data.services.guild_service import guild_service
from data.services.user_service import user_service
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

        user = user_service.get_user(id=member.id)

        if user.is_xp_frozen or user.is_clem:
            return

        level = user.level
        db_guild = guild_service.get_guild()

        roles_to_add = self.assess_new_roles(level, db_guild)
        await self.add_new_roles(member, roles_to_add)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if message.guild.id != cfg.guild_id:
            return
        if message.author.bot:
            return

        db_guild = guild_service.get_guild()
        if message.channel.id == db_guild.channel_botspam:
            return

        user = user_service.get_user(id=message.author.id)
        if user.is_xp_frozen or user.is_clem:
            return

        xp_to_add = randint(0, 11)
        new_xp, level_before = user_service.inc_xp(
            message.author.id, xp_to_add)
        new_level = self.get_level(new_xp)

        if new_level > level_before:
            user_service.inc_level(message.author.id)

        roles_to_add = self.assess_new_roles(new_level, db_guild)
        await self.add_new_roles(message, roles_to_add)

    def assess_new_roles(self, new_level, db):
        roles_to_add = []
        if 15 <= new_level:
            roles_to_add.append(db.role_memberplus)
        if 30 <= new_level:
            roles_to_add.append(db.role_memberpro)
        if 50 <= new_level:
            roles_to_add.append(db.role_memberedition)
        if 75 <= new_level:
            roles_to_add.append(db.role_memberone)
        if 100 <= new_level:
            roles_to_add.append(db.role_memberultra)

        return roles_to_add

    async def add_new_roles(self, obj, roles_to_add):
        if roles_to_add is None:
            return

        member = obj
        if isinstance(obj, discord.Message):
            member = obj.author

        roles_to_add = [member.guild.get_role(role) for role in roles_to_add if member.guild.get_role(
            role) is not None and member.guild.get_role(role) not in member.roles]
        await member.add_roles(*roles_to_add, reason="XP roles")

    def get_level(self, current_xp):
        level = 0
        xp = 0
        while xp <= current_xp:
            xp = xp + 45 * level * (math.floor(level / 10) + 1)
            level += 1
        return level


class StickyRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id != cfg.guild_id:
            return

        roles = [role.id for role in member.roles if role <
                 member.guild.me.top_role and role != member.guild.default_role]
        user_service.set_sticky_roles(member.id, roles)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != cfg.guild_id:
            return

        possible_roles = user_service.get_user(member.id).sticky_roles
        roles = [member.guild.get_role(role) for role in possible_roles if member.guild.get_role(
            role) is not None and member.guild.get_role(role) < member.guild.me.top_role]
        await member.add_roles(*roles, reason="Sticky roles")


async def setup(bot):
    await bot.add_cog(StickyRoles(bot))
    await bot.add_cog(Xp(bot))
