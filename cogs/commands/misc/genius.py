import datetime
import re

import discord
from discord import app_commands
from data.services import guild_service
from discord.ext import commands
from utils import BlooContext, cfg
from utils.framework import genius_or_submod_and_up, whisper_in_general
from utils.framework.transformers import ImageAttachment
from utils.views import issue_autocomplete

# from utils.views.common_issue_modal import CommonIssueModal, EditCommonIssue
# from utils.views.prompt import GenericDescriptionModal


async def prepare_issue_response(title, description, author, buttons=[], image: discord.Attachment = None):
    embed = discord.Embed(title=title)
    embed.color = discord.Color.random()
    embed.description = description
    f = None

    # did the user want to attach an image to this tag?
    if image is not None:
        f = await image.to_file()
        embed.set_image(url=f"attachment://{f.filename}")

    embed.set_footer(text=f"Submitted by {author}")
    embed.timestamp = datetime.datetime.now()

    if not buttons or buttons is None:
        return embed, f, None

    view = discord.ui.View()
    for label, link in buttons:
        # regex match emoji in label
        custom_emojis = re.search(
            r'<:\d+>|<:.+?:\d+>|<a:.+:\d+>|[\U00010000-\U0010ffff]', label)
        if custom_emojis is not None:
            emoji = custom_emojis.group(0).strip()
            label = label.replace(emoji, '')
            label = label.strip()
        else:
            emoji = None
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link, label=label, url=link, emoji=emoji))

    return embed, f, view


class Genius(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = []

    # commonissue = discord.SlashCommandGroup("commonissue", "Interact with common issues", guild_ids=[
    #     cfg.guild_id], permissions=slash_perms.genius_or_submod_and_up())
    common_issue = app_commands.Group(name="tags", description="Interact with tags", guild_ids=[cfg.guild_id])

    # TODO: image only transformer
    # @genius_or_submod_and_up()
    # @common_issue.command(description="Submit a new common issue")
    # @app_commands.describe(title="Title of the issue")
    # @app_commands.describe(image="Image to show in issue")
    # async def new(self, ctx: BlooContext, *, title: str,  image: ImageAttachment = None) -> None:
    #     # get #common-issues channel
    #     channel = ctx.guild.get_channel(
    #         guild_service.get_guild().channel_common_issues)
    #     if not channel:
    #         raise commands.BadArgument("common issues channel not found")

    #     # ensure the attached file is an image
    #     if image is not None:
    #         _type = image.content_type
    #         if _type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
    #             raise commands.BadArgument("Attached file was not an image.")

    #     # prompt the user for common issue body
    #     modal = CommonIssueModal(bot=self.bot, author=ctx.author, title=title)
    #     await ctx.interaction.response.send_modal(modal)
    #     await modal.wait()

    #     description = modal.description
    #     buttons = modal.buttons

    #     if not description:
    #         await ctx.send_warning("Cancelled adding common issue.")
    #         return

    #     embed, f, view = await prepare_issue_response(title, description, ctx.author, buttons, image)

    #     await channel.send(embed=embed, file=f, view=view)
    #     await ctx.send_success("Common issue posted!", delete_after=5, followup=True)
    #     await self.do_reindex(channel)

    # @genius_or_submod_and_up()
    # @commonissue.command(description="Submit a new common issue")
    # async def edit(self, ctx: BlooContext, *, title: Option(str, description="Title of the issue", autocomplete=issue_autocomplete), image: Option(discord.Attachment, required=False, description="Image to show in issue")) -> None:
    #     channel = ctx.guild.get_channel(
    #         guild_service.get_guild().channel_common_issues)
    #     if not channel:
    #         raise commands.BadArgument("common issues channel not found")

    #     if title not in self.bot.issue_cache.cache:
    #         raise commands.BadArgument(
    #             "Issue not found! Title must match one of the embeds exactly, use autocomplete to help!")

    #     message: discord.Message = self.bot.issue_cache.cache[title]

    #     # ensure the attached file is an image
    #     if image is not None:
    #         _type = image.content_type
    #         if _type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
    #             raise commands.BadArgument("Attached file was not an image.")

    #     # prompt the user for common issue body
    #     modal = EditCommonIssue(
    #         bot=self.bot, author=ctx.author, title=title, issue_message=message)
    #     await ctx.interaction.response.send_modal(modal)
    #     await modal.wait()

    #     if not modal.edited:
    #         await ctx.send_warning("Cancelled adding common issue.")
    #         return

    #     description = modal.description
    #     buttons = modal.buttons

    #     embed, f, view = await prepare_issue_response(title, description, ctx.author, buttons, image)
    #     embed.set_footer(text=message.embeds[0].footer.text)
    #     await message.edit(embed=embed, file=f or discord.MISSING, attachments=[], view=view)
    #     await ctx.send_success("Common issue edited!", delete_after=5, followup=True)
    #     await self.do_reindex(channel)

    # @genius_or_submod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Post an embed", permissions=slash_perms.genius_or_submod_and_up())
    # async def postembed(self, ctx: BlooContext, *, title: Option(str, description="Title of the embed"), image: Option(discord.Attachment, required=False, description="Image to show in embed")):
    #     """Post an embed in the current channel (Geniuses only)

    #     Example usage
    #     ------------
    #     /postembed This is a title (you will be prompted for a description)

    #     Parameters
    #     ----------
    #     title : str
    #         "Title for the embed"

    #     """

    #     # get #common-issues channel
    #     channel = ctx.channel

    #     # ensure the attached file is an image
    #     if image is not None:
    #         _type = image.content_type
    #         if _type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
    #             raise commands.BadArgument("Attached file was not an image.")

    #     # prompt the user for common issue body
    #     modal = GenericDescriptionModal(
    #         author=ctx.author, title=f"New embed — {title}")
    #     await ctx.interaction.response.send_modal(modal)
    #     await modal.wait()

    #     description = modal.value
    #     if not description:
    #         await ctx.send_warning("Cancelled new embed.")
    #         return

    #     embed, f, _ = await prepare_issue_response(title, description, ctx.author, image)
    #     await channel.send(embed=embed, file=f)

    # @genius_or_submod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Repost common-issues table of contents", permissions=slash_perms.genius_or_submod_and_up())
    # async def reindexissues(self, ctx: BlooContext):
    #     # get #common-issues channel
    #     channel: discord.TextChannel = ctx.guild.get_channel(
    #         guild_service.get_guild().channel_common_issues)
    #     if not channel:
    #         raise commands.BadArgument("common issues channel not found")

    #     await ctx.defer(ephemeral=True)
    #     res = await self.do_reindex(channel)

    #     if res is None:
    #         raise commands.BadArgument("Something unexpected occured")

    #     count, page = res
    #     await ctx.send_success(f"Indexed {count} issues and posted {page} Table of Contents embeds!")

    # async def do_reindex(self, channel):
    #     contents = {}
    #     async for message in channel.history(limit=None, oldest_first=True):
    #         if message.author.id != self.bot.user.id:
    #             continue

    #         if not message.embeds:
    #             continue

    #         embed = message.embeds[0]
    #         if not embed.footer.text:
    #             continue

    #         if embed.footer.text.startswith("Submitted by"):
    #             contents[f"{embed.title}"] = message
    #         elif embed.footer.text.startswith("Table of Contents"):
    #             await message.delete()
    #         else:
    #             continue

    #     page = 1
    #     count = 1
    #     toc_embed = discord.Embed(
    #         title="Table of Contents", description="Click on a link to jump to the issue!\n", color=discord.Color.gold())
    #     toc_embed.set_footer(text=f"Table of Contents • Page {page}")
    #     for title, message in contents.items():
    #         this_line = f"\n{count}. [{title}]({message.jump_url})"
    #         count += 1
    #         if len(toc_embed.description) + len(this_line) < 4096:
    #             toc_embed.description += this_line
    #         else:
    #             await channel.send(embed=toc_embed)
    #             page += 1
    #             toc_embed.description = ""
    #             toc_embed.title = ""
    #             toc_embed.set_footer(text=f"Table of Contents • Page {page}")

    #     self.bot.issue_cache.cache = contents
    #     await channel.send(embed=toc_embed)
    #     return count, page

    # @genius_or_submod_and_up()
    # @slash_command(guild_ids=[cfg.guild_id], description="Post raw body of an embed", permissions=slash_perms.genius_or_submod_and_up())
    # async def rawembed(self, ctx: BlooContext, *, channel: Option(discord.TextChannel, description="Channel the embed is in"), message_id: Option(str, description="ID of the message with the embed"), mobile_friendly: Option(bool, description="Whether to display the tag in a mobile friendly format")):
    #     try:
    #         message_id = int(message_id)
    #     except:
    #         raise commands.BadArgument("Invalid message ID!")

    #     try:
    #         message: discord.Message = await channel.fetch_message(message_id)
    #     except Exception:
    #         raise commands.BadArgument(
    #             "Could not find a message with that ID!")

    #     if message.author != ctx.me:
    #         raise commands.BadArgument("I didn't post that embed!")

    #     if len(message.embeds) == 0:
    #         raise commands.BadArgument("Message does not have an embed!")

    #     _file = message.embeds[0].image
    #     response = discord.utils.escape_markdown(
    #         message.embeds[0].description) if not mobile_friendly else message.embeds[0].description
    #     parts = [response[i:i+2000] for i in range(0, len(response), 2000)]

    #     for i, part in enumerate(parts):
    #         if i == 0:
    #             await ctx.respond(part, allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
    #         else:
    #             await ctx.send(part, allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

    #     if _file:
    #         await ctx.send(_file.url, allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

    # @whisper_in_general()
    # @slash_command(guild_ids=[cfg.guild_id], description="Post the embed for one of the common issues")
    # async def issue(self, ctx: BlooContext, title: Option(str, autocomplete=issue_autocomplete), user_to_mention: Option(discord.Member, description="User to mention in the response", required=False)):
    #     if title not in self.bot.issue_cache.cache:
    #         raise commands.BadArgument(
    #             "Issue not found! Title must match one of the embeds exactly, use autocomplete to help!")

    #     message: discord.Message = self.bot.issue_cache.cache[title]
    #     embed = message.embeds[0]
    #     view = discord.ui.View()
    #     components = message.components
    #     if components:
    #         for component in components:
    #             if isinstance(component, discord.ActionRow):
    #                 for child in component.children:
    #                     b = discord.ui.Button(
    #                         style=child.style, emoji=child.emoji, label=child.label, url=child.url)
    #                     view.add_item(b)

    #     if user_to_mention is not None:
    #         title = f"Hey {user_to_mention.mention}, have a look at this!"
    #     else:
    #         title = None

    #     await ctx.respond_or_edit(content=title, embed=embed, ephemeral=ctx.whisper, view=view)


async def setup(bot):
    await bot.add_cog(Genius(bot))
