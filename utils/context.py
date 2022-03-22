import asyncio
import functools
from typing import Optional
import discord


def transform_context(func: discord.app_commands.Command):
    @functools.wraps(func)
    async def decorator(self, interaction, *args, **kwargs):
        ctx = BlooContext(interaction)
        return await func(self, ctx, *args, **kwargs)

    return decorator


class BlooContext:
    def __init__(self, interaction: discord.Interaction):
        self.interaction: discord.Interaction = interaction
        self.whisper = False

    @property
    def guild(self):
        return self.interaction.guild

    @property
    def channel(self):
        return self.interaction.channel

    @property
    def author(self):
        return self.interaction.user

    @property
    def respond(self):
        if self.interaction.response.is_done():
            return self.interaction.followup.send
        else:
            return self.interaction.response.send_message

    @property
    def followup(self):
        return self.interaction.followup

    @property
    def edit(self):
        return self.interaction.edit_original_message

    @property
    def bot(self):
        return self.interaction.client

    async def respond_or_edit(self, *args, **kwargs):
        """Respond to an interaction if not already responded, otherwise edit the original response.
        Takes in the same args and kwargs as `respond`.
        """

        if self.interaction.response.is_done():
            if kwargs.get("followup") or self.interaction.message is None:
                if kwargs.get("view") is None:
                    kwargs["view"] = discord.utils.MISSING
                del kwargs["followup"]

                delete_after = kwargs.get("delete_after")
                if "delete_after" in kwargs:
                    del kwargs["delete_after"]

                test = await self.followup.send(*args, **kwargs)
                if not kwargs.get("ephemeral") and delete_after is not None:
                    await test.delete(delay=delete_after)
                return

            if kwargs.get("ephemeral") is not None:
                del kwargs["ephemeral"]
            if "delete_after" in kwargs:
                del kwargs["delete_after"]
            if "followup" in kwargs:
                del kwargs["followup"]

            return await self.edit(*args, **kwargs)
        else:
            if "followup" in kwargs:
                del kwargs["followup"]
            
            delete_after = kwargs.get("delete_after")
            if "delete_after" in kwargs:
                del kwargs["delete_after"]

            await self.respond(*args, **kwargs)
            if not kwargs.get("ephemeral") and delete_after is not None:
                await asyncio.sleep(delete_after)
                await self.interaction.delete_original_message()

    async def send_followup(self, *args, **kwargs):
        delete_after = kwargs.get("delete_after")
        if "delete_after" in kwargs:
            del kwargs["delete_after"]

        response = await self.followup.send(*args, **kwargs)
        if not kwargs.get("ephemeral") and delete_after is not None:
            await response.delete(delay=delete_after)

    async def send_success(self, description: str, title:Optional[str] = None, delete_after: Optional[float] = None, followup: Optional[bool] = None):
        """Send an embed response with green color to an interaction.

        Parameters
        ----------
        description : str
            Description of the embed
        title : Optional[str], optional
            Title of the embed, by default None
        delete_after : Optional[float], optional
            Number of seconds to delete the embed after (only if not responding ephemerally), by default None
        followup : Optional[bool], optional
            Whether to send this as a followup to the original response, by default None
        """

        embed = discord.Embed(title=title, description=description,  color=discord.Color.dark_green())
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper, view=discord.utils.MISSING, delete_after=delete_after, followup=followup)

    async def send_warning(self, description: str, title:Optional[str] = None, delete_after: Optional[float] = None, followup: Optional[bool] = None):
        """Send an embed response with orange color to an interaction.

        Parameters
        ----------
        description : str
            Description of the embed
        title : Optional[str], optional
            Title of the embed, by default None
        delete_after : Optional[float], optional
            Number of seconds to delete the embed after (only if not responding ephemerally), by default None
        followup : Optional[bool], optional
            Whether to send this as a followup to the original response, by default None
        """

        embed = discord.Embed(title=title, description=description,  color=discord.Color.orange())
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper, view=discord.utils.MISSING, delete_after=delete_after, followup=followup)

    async def send_error(self, description: str, title:Optional[str] = ":(\nYour command ran into a problem", delete_after: Optional[float] = None, followup: Optional[bool] = None):
        """Send an embed response with red color to an interaction.

        Parameters
        ----------
        description : str
            Description of the embed
        title : Optional[str], optional
            Title of the embed, by default None
        delete_after : Optional[float], optional
            Number of seconds to delete the embed after (only if not responding ephemerally), by default None
        followup : Optional[bool], optional
            Whether to send this as a followup to the original response, by default None
        """

        embed = discord.Embed(title=title, description=description,  color=discord.Color.red())
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper, view=discord.utils.MISSING, delete_after=delete_after, followup=followup)
