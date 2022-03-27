import asyncio
import functools
from datetime import datetime, timedelta
from typing import Optional

import discord
import pytimeparse
from discord.ext import commands

from .jobs import Tasks


def transform_context(func: discord.app_commands.Command):
    @functools.wraps(func)
    async def decorator(self, interaction, *args, **kwargs):
        ctx = BlooContext(interaction)
        return await func(self, ctx, *args, **kwargs)

    return decorator


class PromptData:
    def __init__(self, value_name, description, convertor=None, timeout=120, title="", reprompt=False, raw=False):
        self.value_name = value_name
        self.description = description
        self.convertor = convertor
        self.title = title
        self.reprompt = reprompt
        self.timeout = timeout
        self.raw = raw

    def __copy__(self):
        return PromptData(self.value_name, self.description, self.convertor, self.title, self.reprompt)


class PromptDataReaction:
    def __init__(self, message, reactions, timeout=None, delete_after=False, raw_emoji=False):
        self.message = message
        self.reactions = reactions
        self.timeout = timeout
        self.delete_after = delete_after
        self.raw_emoji = raw_emoji


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
    def defer(self):
        return self.interaction.response.defer

    @property
    def followup(self):
        return self.interaction.followup

    @property
    def edit(self):
        return self.interaction.edit_original_message

    @property
    def bot(self):
        return self.interaction.client

    @property
    def me(self):
        return self.interaction.guild.me

    @property
    def send(self):
        return self.interaction.channel.send

    @property
    def tasks(self) -> Tasks:
        return self.bot.tasks

    async def respond_or_edit(self, *args, **kwargs):
        """Respond to an interaction if not already responded, otherwise edit the original response.
        Takes in the same args and kwargs as `respond`.
        """

        # if self.interaction.response.is_done():
        #     print("?")
        #     if kwargs.get("followup"):
        #         if kwargs.get("view") is None:
        #             kwargs["view"] = discord.utils.MISSING

        #         if "followup" in kwargs:
        #             del kwargs["followup"]

        #         delete_after = kwargs.get("delete_after")
        #         if "delete_after" in kwargs:
        #             del kwargs["delete_after"]

        #         test = await self.followup.send(*args, **kwargs)
        #         if not kwargs.get("ephemeral") and delete_after is not None:
        #             await test.delete(delay=delete_after)
        #         return

        #     ephemeral = kwargs.get("ephemeral")
        #     if kwargs.get("ephemeral") is not None:
        #         del kwargs["ephemeral"]
        #     delete_after = kwargs.get("delete_after")
        #     if "delete_after" in kwargs:
        #         del kwargs["delete_after"]
        #     if "followup" in kwargs:
        #         del kwargs["followup"]

        #     await self.edit(*args, **kwargs)
        #     if delete_after and not ephemeral:
        #         await asyncio.sleep(delete_after)
        #         await self.interaction.delete_original_message()
        # else:
        #     if "followup" in kwargs:
        #         del kwargs["followup"]
        #     delete_after = kwargs.get("delete_after")
        #     if "delete_after" in kwargs:
        #         del kwargs["delete_after"]
        #     res = await self.respond(*args, **kwargs)
        #     if not kwargs.get("ephemeral") and delete_after is not None:
        #         await asyncio.sleep(delete_after)
        #         await self.interaction.delete_original_message()
        
        if self.interaction.response.is_done(): # we've responded to the interaction already
            if not kwargs.get("followup"): # is there a message to edit and do we want to edit it?
                ephemeral = kwargs.get("ephemeral")
                if kwargs.get("ephemeral") is not None:
                    del kwargs["ephemeral"]
                delete_after = kwargs.get("delete_after")
                if "delete_after" in kwargs:
                    del kwargs["delete_after"]
                if "followup" in kwargs:
                    del kwargs["followup"]
                if kwargs.get("view") is discord.utils.MISSING:
                    kwargs["view"] = None
                await self.edit(*args, **kwargs)
                if delete_after and not ephemeral:
                    self.bot.loop.create_task(self.delay_delete(self.interaction, delete_after))
            else: # we probably want to do a followup
                if kwargs.get("view") is None:
                    kwargs["view"] = discord.utils.MISSING

                if "followup" in kwargs:
                    del kwargs["followup"]

                delete_after = kwargs.get("delete_after")
                if "delete_after" in kwargs:
                    del kwargs["delete_after"]
                test = await self.followup.send(*args, **kwargs)
                if delete_after is not None:
                    try:
                        await test.delete(delay=delete_after)
                    except:
                        pass
        else: #first time responding to this
            if "followup" in kwargs:
                del kwargs["followup"]
            delete_after = kwargs.get("delete_after")
            if "delete_after" in kwargs:
                del kwargs["delete_after"]
            await self.respond(*args, **kwargs)
            if not kwargs.get("ephemeral") and delete_after is not None:
                self.bot.loop.create_task(self.delay_delete(self.interaction, delete_after))

    async def delay_delete(self, ctx: discord.Interaction, delay: int):
        try:
            await asyncio.sleep(delay)
            await ctx.delete_original_message()
        except:
            pass

    async def send_followup(self, *args, **kwargs):
        delete_after = kwargs.get("delete_after")
        if "delete_after" in kwargs:
            del kwargs["delete_after"]

        response = await self.followup.send(*args, **kwargs)
        if not kwargs.get("ephemeral") and delete_after is not None:
            await response.delete(delay=delete_after)

    async def send_success(self, description: str, title: Optional[str] = None, delete_after: Optional[float] = None, followup: Optional[bool] = None, ephemeral: Optional[bool] = False):
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

        embed = discord.Embed(
            title=title, description=description,  color=discord.Color.dark_green())
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper or ephemeral, view=discord.utils.MISSING, delete_after=delete_after, followup=followup)

    async def send_warning(self, description: str, title: Optional[str] = None, delete_after: Optional[float] = None, followup: Optional[bool] = None, ephemeral: Optional[bool] = False):
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

        embed = discord.Embed(
            title=title, description=description,  color=discord.Color.orange())
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper or ephemeral, view=discord.utils.MISSING, delete_after=delete_after, followup=followup)

    async def send_error(self, description: str, title: Optional[str] = ":(\nYour command ran into a problem", delete_after: Optional[float] = None, followup: Optional[bool] = None, whisper: Optional[bool] = False):
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

        embed = discord.Embed(
            title=title, description=description,  color=discord.Color.red())
        return await self.respond_or_edit(content="", embed=embed, ephemeral=self.whisper or whisper, view=discord.utils.MISSING, delete_after=delete_after, followup=followup)

    async def prompt(self, info: PromptData):
        """Prompts for a response
        
        Parameters
        ----------
        info : PromptData
            "Prompt information"

        """
        def wait_check(m):
            return m.author == self.author and m.channel == self.channel
    
        ret = None
        embed = discord.Embed(title=info.title if not info.reprompt else f"That wasn't a valid {info.value_name}. {info.title if info.title is not None else ''}", description=info.description, color=discord.Color.blurple() if not info.reprompt else discord.Color.orange())
        embed.set_footer(text="Send 'cancel' to cancel.")

        await self.respond_or_edit(content="", embed=embed, ephemeral=True, view=None)
        try:
            response = await self.bot.wait_for('message', check=wait_check, timeout=info.timeout)
        except asyncio.TimeoutError:
            await self.send_warning("Timed out.", delete_after=5)
        else:
            try:
                await response.delete()
            except:
                pass
            if response.content.lower() == "cancel":
                await self.send_warning("Cancelled.", delete_after=5)
                return
            elif not response.content and info.convertor is not None:
                info.reprompt = True
                return await self.prompt(info)
            else:
                if info.convertor in [str, int, pytimeparse.parse]:
                    try:
                        if info.raw:
                            ret = info.convertor(response.content), response
                        else:
                            ret = info.convertor(response.content)
                    except Exception:
                        ret = None
                    
                    if ret is None:
                        info.reprompt = True
                        return await self.prompt(info)

                    if info.convertor is pytimeparse.parse:
                        now = datetime.now()
                        time = now + timedelta(seconds=ret)
                        if time < now:
                            raise commands.BadArgument("Time has to be in the future >:(")

                else:
                    if info.convertor is not None:
                        value = await info.convertor(self, response.content)
                    else:
                        value = response.content

                    if info.raw:
                        ret = value, response
                    else:
                        ret = value
                    
        return ret
    
    async def prompt_reaction(self, info: PromptDataReaction):
        """Prompts for a reaction
        
        Parameters
        ----------
        info : PromptDataReaction
            "Prompt data"
            
        """
        for reaction in info.reactions:
            await info.message.add_reaction(reaction)
            
        def wait_check(reaction, user):
            res = (user.id != self.bot.user.id
                and reaction.message.id == info.message.id)
            
            if info.reactions:
                res = res and str(reaction.emoji) in info.reactions
            
            return res
            
        if info.timeout is None:
            while True:
                try:
                    reaction, reactor = await self.bot.wait_for('reaction_add', timeout=300.0, check=wait_check)
                    if reaction is not None:
                        return str(reaction.emoji), reactor    
                except asyncio.TimeoutError:
                    if self.bot.report.pending_tasks.get(info.message.id) == "TERMINATE":
                        return "TERMINATE", None
        else:
            try:
                reaction, reactor = await self.bot.wait_for('reaction_add', timeout=info.timeout, check=wait_check)
            except asyncio.TimeoutError:
                try:
                    if info.delete_after:
                        await info.message.delete()
                    else:
                        await info.message.clear_reactions()
                    return None, None
                except Exception:
                    pass
            else:
                if info.delete_after:
                    await info.message.delete()
                else:
                    await info.message.clear_reactions()
                
                if not info.raw_emoji:
                    return str(reaction.emoji), reactor    
                else:
                    return reaction, reactor    


class BlooOldContext(commands.Context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks: Tasks = self.bot.tasks

    async def prompt(self, info: PromptData):
        def wait_check(m):
            return m.author == self.author and m.channel == self.channel

        ret = None
        embed = discord.Embed(
            title=info.title if not info.reprompt else f"That wasn't a valid {info.value_name}. {info.title if info.title is not None else ''}",
            description=info.description,
            color=discord.Color.blurple() if not info.reprompt else discord.Color.orange())
        embed.set_footer(text="Send 'cancel' to cancel.")

        prompt_msg = await self.send(embed=embed)
        try:
            response = await self.bot.wait_for('message', check=wait_check, timeout=info.timeout)
        except asyncio.TimeoutError:
            await prompt_msg.delete()
            return
        else:
            await response.delete()
            await prompt_msg.delete()
            if response.content.lower() == "cancel":
                return
            elif not response.content:
                info.reprompt = True
                return await self.prompt(info)
            else:
                if info.convertor in [str, int, pytimeparse.parse]:
                    try:
                        ret = info.convertor(response.content)
                    except Exception:
                        ret = None

                    if ret is None:
                        info.reprompt = True
                        return await self.prompt(info)

                    if info.convertor is pytimeparse.parse:
                        now = datetime.now()
                        time = now + timedelta(seconds=ret)
                        if time < now:
                            raise commands.BadArgument(
                                "Time has to be in the future >:(")

                else:
                    ret = await info.convertor(self, response.content)

        return ret

    async def prompt_reaction(self, info: PromptDataReaction):
        for reaction in info.reactions:
            await info.message.add_reaction(reaction)

        def wait_check(reaction, user):
            res = (user.id != self.bot.user.id
                   and reaction.message == info.message)

            if info.reactions:
                res = res and str(reaction.emoji) in info.reactions

            return res

        if info.timeout is None:
            while True:
                try:
                    reaction, reactor = await self.bot.wait_for('reaction_add', timeout=300.0, check=wait_check)
                    if reaction is not None:
                        return str(reaction.emoji), reactor
                except asyncio.TimeoutError:
                    if self.bot.report.pending_tasks.get(info.message.id) == "TERMINATE":
                        return "TERMINATE", None
        else:
            try:
                reaction, reactor = await self.bot.wait_for('reaction_add', timeout=info.timeout, check=wait_check)
            except asyncio.TimeoutError:
                try:
                    if info.delete_after:
                        await info.message.delete()
                    else:
                        await info.message.clear_reactions()
                    return None, None
                except Exception:
                    pass
            else:
                if info.delete_after:
                    await info.message.delete()
                else:
                    await info.message.clear_reactions()

                if not info.raw_emoji:
                    return str(reaction.emoji), reactor
                else:
                    return reaction, reactor

    async def send_warning(self, description: str, title="", delete_after: int = None):
        return await self.reply(embed=discord.Embed(title=title, description=description, color=discord.Color.orange()), delete_after=delete_after)

    async def send_success(self, description: str, title="", delete_after: int = None):
        return await self.reply(embed=discord.Embed(title=title, description=description, color=discord.Color.dark_green()), delete_after=delete_after)

    async def send_error(self, error):
        embed = discord.Embed(title=":(\nYour command ran into a problem")
        embed.color = discord.Color.red()
        embed.description = str(error)
        await self.send(embed=embed, delete_after=8)
