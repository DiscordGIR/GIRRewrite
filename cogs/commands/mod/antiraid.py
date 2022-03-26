import discord
from discord.ext import commands
from discord import app_commands

from data.services import guild_service, user_service
from utils import cfg, BlooContext, transform_context
from utils.framework import admin_and_up, mod_and_up
from utils.views import Confirm, GenericDescriptionModal


class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Add a new phrase to the raid filter")
    @app_commands.describe(phrase="Phrase to add")
    @transform_context
    async def raid(self, ctx: BlooContext, phrase: str) -> None:
        # these are phrases that when said by a whitename, automatically bans them.
        # for example: known scam URLs
        done = guild_service.add_raid_phrase(phrase)
        if not done:
            raise commands.BadArgument("That phrase is already in the list.")
        else:
            await ctx.send_success(description=f"Added `{phrase}` to the raid phrase list!", delete_after=5)

    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Add a list of (newline-separated) phrases to the raid filter.")
    @transform_context
    async def batchraid(self, ctx: BlooContext) -> None:
        modal = GenericDescriptionModal(ctx, author=ctx.author, title=f"New sub news post")
        await ctx.interaction.response.send_modal(modal)
        await modal.wait()

        phrases = modal.value
        if not phrases:
            await ctx.send_warning("Cancelled adding new raid phrases.", followup=True)
            return

        await ctx.interaction.response.defer()
        phrases = list(set(phrases.split("\n")))
        phrases = [phrase.strip() for phrase in phrases if phrase.strip()]

        phrases_contenders = set(phrases)
        phrases_already_in_db = set([phrase.word for phrase in guild_service.get_guild().raid_phrases])

        duplicate_count = len(phrases_already_in_db & phrases_contenders) # count how many duplicates we have
        new_phrases = list(phrases_contenders - phrases_already_in_db)

        if not new_phrases:
            raise commands.BadArgument("All the phrases you supplied are already in the database.")

        phrases_prompt_string = "\n".join([f"**{i+1}**. {phrase}" for i, phrase in enumerate(new_phrases)])
        if len(phrases_prompt_string) > 3900:
            phrases_prompt_string = phrases_prompt_string[:3500] + "\n... (and some more)"

        embed = discord.Embed(title="Confirm raidphrase batch",
                        color=discord.Color.dark_orange(),
                        description=f"{phrases_prompt_string}\n\nShould we add these {len(new_phrases)} phrases?")

        if duplicate_count > 0:
            embed.set_footer(text=f"Note: we found {duplicate_count} duplicates in your list.")

        view = Confirm(ctx)
        await ctx.respond_or_edit(embed=embed, view=view, ephemeral=True, followup=True)
        await view.wait()
        do_add = view.value

        if do_add:
            await ctx.interaction.response.defer()
            for phrase in new_phrases:
                guild_service.add_raid_phrase(phrase)

            await ctx.send_success(f"Added {len(new_phrases)} phrases to the raid filter.", followup=True)
        else:
            await ctx.send_warning("Cancelled.", followup=True)

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Remove a phrase from the raid filter.")
    @app_commands.describe(phrase="Phrase to remove")
    @transform_context
    async def removeraid(self, ctx: BlooContext, phrase: str) -> None:
        word = phrase.lower()

        words = guild_service.get_guild().raid_phrases
        words = list(filter(lambda w: w.word.lower() == word.lower(), words))

        if len(words) > 0:
            guild_service.remove_raid_phrase(words[0].word)
            await ctx.send_success("Deleted!", delete_after=5)
        else:
            raise commands.BadArgument("That word is not a raid phrase.")

    @mod_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Toggle banning of *today's* new accounts in join spam detector.")
    @app_commands.describe(mode="True if you want to ban, false otherwise")
    @transform_context
    async def spammode(self, ctx: BlooContext, mode: bool = None) -> None:
        if mode is None:
            mode = not guild_service.get_guild().ban_today_spam_accounts

        guild_service.set_spam_mode(mode)
        await ctx.send_success(description=f"We {'**will ban**' if mode else 'will **not ban**'} accounts created today in join spam filter.")

    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Verify a user so they won't be banned by antiraid filters.")
    @app_commands.describe(user="User to verify")
    @app_commands.describe(mode="True if you want to verify, false otherwise")
    @transform_context
    async def verify(self, ctx: BlooContext, user: discord.Member, mode: bool = None) -> None:
        profile = user_service.get_user(user.id)
        if mode is None:
            profile.raid_verified = not profile.raid_verified
        else:
            profile.raid_verified = mode

        profile.save()

        await ctx.send_success(description=f"{'**Verified**' if profile.raid_verified else '**Unverified**'} user {user.mention}.")

    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Lock a channel")
    @app_commands.describe(channel="Channel to lock")
    @transform_context
    async def lock(self, ctx: BlooContext, channel: discord.TextChannel = None):
        await ctx.interaction.response.defer()
        if channel is None:
            channel = ctx.channel
            
        if await self.lock_unlock_channel(ctx, channel, True) is not None:
            await ctx.send_success(f"Locked {channel.mention}!")
        else:
            raise commands.BadArgument(f"{channel.mention} already locked or my permissions are wrong.")

    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock")
    @transform_context
    async def unlock(self,  ctx: BlooContext, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel
            
        if await self.lock_unlock_channel(ctx, channel) is not None:
            await ctx.send_success(f"Unlocked {channel.mention}!")
        else:
            raise commands.BadArgument(f"{channel.mention} already unlocked or my permissions are wrong.")

    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Mark a channel as automatically freezable during a raid")
    @app_commands.describe(channel="Channel to mark as freezable")
    @transform_context
    async def freezeable(self,  ctx: BlooContext, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        if channel.id in guild_service.get_locked_channels():
            raise commands.BadArgument("That channel is already lockable.")
        
        guild_service.add_locked_channels(channel.id)
        await ctx.send_success(f"Added {channel.mention} as lockable channel!")

    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Unmark a channel as freezable during a raid")
    @app_commands.describe(channel="Channel to unmark as freezable")
    @transform_context
    async def unfreezeable(self,  ctx: BlooContext, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        if channel.id not in guild_service.get_locked_channels():
            raise commands.BadArgument("That channel isn't already lockable.")
        
        guild_service.remove_locked_channels(channel.id)
        await ctx.send_success(f"Removed {channel.mention} as lockable channel!")
            
    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Freeze all channels")
    @transform_context
    async def freeze(self, ctx):
        channels = guild_service.get_locked_channels()
        if not channels:
            raise commands.BadArgument("No freezeable channels! Set some using `/freezeable`.")
        
        locked = []
        await ctx.defer()
        for channel in channels:
            channel = ctx.guild.get_channel(channel)
            if channel is not None:
                if await self.lock_unlock_channel(ctx, channel, lock=True):
                    locked.append(channel)
        
        if locked:              
            await ctx.send_success(f"Locked {len(locked)} channels!")
        else:
            raise commands.BadArgument("Server is already locked or my permissions are wrong.")
        
    
    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Unfreeze all channels")
    @transform_context
    async def unfreeze(self, ctx):
        channels = guild_service.get_locked_channels()
        if not channels:
            raise commands.BadArgument("No unfreezeable channels! Set some using `/freezeable`.")
        
        unlocked = []
        await ctx.defer()
        for channel in channels:
            channel = ctx.guild.get_channel(channel)
            if channel is not None:
                if await self.lock_unlock_channel(ctx, channel, lock=None):
                    unlocked.append(channel)
        
        if unlocked:              
            await ctx.send_success(f"Unlocked {len(unlocked)} channels!")
        else:
            raise commands.BadArgument("Server is already unlocked or my permissions are wrong.")

    async def lock_unlock_channel(self,  ctx: BlooContext, channel, lock=None):
        db_guild = guild_service.get_guild()
        
        default_role = ctx.guild.default_role
        member_plus = ctx.guild.get_role(db_guild.role_memberplus)   
        
        default_perms = channel.overwrites_for(default_role)
        memberplus_perms = channel.overwrites_for(member_plus)

        if lock and default_perms.send_messages is None and memberplus_perms.send_messages is None:
            default_perms.send_messages = False
            memberplus_perms.send_messages = True
        elif lock is None and (not default_perms.send_messages) and memberplus_perms.send_messages:
            default_perms.send_messages = None
            memberplus_perms.send_messages = None
        else:
            return
        
        try:
            await channel.set_permissions(default_role, overwrite=default_perms, reason="Locked!" if lock else "Unlocked!")
            await channel.set_permissions(member_plus, overwrite=memberplus_perms, reason="Locked!" if lock else "Unlocked!")
            return True
        except Exception:
            return


async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
