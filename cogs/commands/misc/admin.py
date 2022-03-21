import discord
from discord import app_commands
from discord.ext import commands
from utils import BlooContext, cfg, transform_context
from utils.framework import admin_and_up


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # TODO: image only transformer
    @admin_and_up()
    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="Change the bot's profile picture")
    @app_commands.describe(image="Image to use as profile picture")
    @transform_context
    async def setpfp(self, ctx: BlooContext, image: discord.Attachment):
        if image is None or image.content_type not in ["image/png", "image/jpeg", "image/webp"]:
            raise commands.BadArgument(
                "Please attach an image to use as the profile picture.")

        await self.bot.user.edit(avatar=await image.read())
        await ctx.send_success("Done!", delete_after=5)


async def setup(bot):
    await bot.add_cog(Admin(bot))
