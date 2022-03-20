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
    def respond(self):
        if self.interaction.response.is_done():
            return self.interaction.followup.send
        else:
            return self.interaction.response.send_message

    @property
    def edit(self):
        return self.interaction.edit_original_message

    async def respond_or_edit(self, *args, **kwargs):
        """Respond to an interaction if not already responded, otherwise edit the original response.
        Takes in the same args and kwargs as `respond`.
        """

        if self.interaction.response.is_done():
            if kwargs.get("followup"):
                if kwargs.get("view") is None:
                    kwargs["view"] = discord.utils.MISSING
                del kwargs["followup"]
                return await self.followup.send(*args, **kwargs)

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

            return await self.respond(*args, **kwargs)

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
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper, view=None, delete_after=delete_after, followup=followup)

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
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper, view=None, delete_after=delete_after, followup=followup)

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
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper, view=None, delete_after=delete_after, followup=followup)
