import discord
from discord import app_commands
from discord.ext import commands
from utils import cfg, BlooContext, transform_context
from utils.framework import whisper


class Greetings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None

    # up here you can define permission checks 
    # i.e mod_and_up()
    @app_commands.guilds(cfg.guild_id) # declare guilds this command can be used in
    @app_commands.command(description="Says hello to the user") # add command to the tree
    @app_commands.describe(message="The message to send back") # add description to arguments
    @transform_context # this is to turn the interaction object d.py gives into a Context object (ORDER IS IMPORTANT!)
    @whisper # make response ephemeral for non mods (ORDER IS IMPORTANT!
    async def say(self, ctx: BlooContext, message: str):
        await ctx.send_success(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(Greetings(bot))
