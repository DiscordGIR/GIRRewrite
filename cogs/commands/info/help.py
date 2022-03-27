import typing
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Command, Group

from setuptools import Command
from data.services.guild_service import guild_service
from utils import cfg, BlooContext, transform_context
from utils.framework import whisper, gatekeeper
from utils.views import command_list_autocomplete

# TODO: This whole thing needs work
class Utilities(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.left_col_length = 17
        self.right_col_length = 80
        self.mod_only = ["ModActions", "ModUtils", "Filters", "BoosterEmojis", "RoleAssignButtons", "Giveaway", "Admin", "AntiRaid", "Trivia"]
        self.genius_only = ["Genius"]

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="View all my cogs and commands.")
    @app_commands.describe(command_name="The name of the command to get info of")
    @app_commands.autocomplete(command_name=command_list_autocomplete)
    @transform_context
    async def help(self, ctx: BlooContext, *, command_name: str = None) -> None:
        """Gets all my cogs and commands."""

        if not command_name:
            await ctx.respond('📬', ephemeral=True)
            header = "Get a detailed description for a specific command with `/help <command name>`\n"
            string = ""

            for cog_name in self.bot.cogs:
                cog = self.bot.cogs[cog_name]
                is_admin = gatekeeper.has(ctx.guild, ctx.author, 6)
                is_mod = gatekeeper.has(ctx.guild, ctx.author, 5)
                is_genius = gatekeeper.has(ctx.guild, ctx.author, 4)
                submod = ctx.guild.get_role(guild_service.get_guild().role_sub_mod)

                if not cog.__cog_app_commands__:
                    continue
                elif cog_name in self.mod_only and not is_mod:
                    continue
                elif cog_name in self.genius_only and not is_genius:
                    continue
                elif cog_name == "SubNews" and not (submod in ctx.author.roles or is_admin):
                    continue
                
                string += f"== {cog_name} ==\n"

                for command in cog.__cog_app_commands__:
                    if isinstance(command, discord.app_commands.ContextMenu):
                        continue

                    command: typing.Union[app_commands.Command, app_commands.Group] = command
                    spaces_left = ' ' * (self.left_col_length - len(command.name))
                    if command.description is not None:
                        command.brief = command.description.split("\n")[0]
                    else:
                        command.brief = "No description."
                    cmd_desc = command.brief[0:self.right_col_length] + "..." if len(command.brief) > self.right_col_length else command.brief

                    if isinstance(command, app_commands.Group):
                        string += f"\t* {command.name}{spaces_left} :: {cmd_desc}\n"
                        for c in command.commands:
                            spaces_left = ' ' * (self.left_col_length - len(c.name)-4)
                            if c.description is not None:
                                c.brief = c.description.split("\n")[0]
                            else:
                                c.brief = "No description."
                            cmd_desc = c.brief[0:self.right_col_length] + "..." if len(c.brief) > self.right_col_length else c.brief
                            string += f"\t\t* {c.name}{spaces_left} :: {cmd_desc}\n"
                    else:
                        string += f"\t* {command.name}{spaces_left} :: {cmd_desc}\n"

                string += "\n"

            try:
                parts = string.split("\n")
                group_size = 25
                if len(parts) <= group_size:
                    await ctx.author.send(header + "\n```asciidoc\n" + "\n".join(parts[0:group_size]) + "```")
                else:
                    seen = 0
                    await ctx.author.send(header + "\n```asciidoc\n" + "\n".join(parts[seen:seen+group_size]) + "```")
                    seen += group_size
                    while seen < len(parts):
                        await ctx.author.send("```asciidoc\n" + "\n".join(parts[seen:seen+group_size]) + "```")
                        seen += group_size
                        
            except Exception:
                raise commands.BadArgument("I tried to DM you but couldn't. Make sure your DMs are enabled.")

        else:
            command: typing.Union[app_commands.Command, app_commands.Group] = self.bot.tree.get_command(command_name.split()[0].lower(), guild=ctx.guild)
            if command:
                if isinstance(command, app_commands.Group):
                    command = command.get_command(command_name.split()[1].lower())

                embed = await self.get_usage_embed(ctx, command)
                try:
                    await ctx.author.send(embed=embed)
                    await ctx.respond('📬', ephemeral=True)
                except Exception:
                    raise commands.BadArgument("I tried to DM you but couldn't. Make sure your DMs are enabled.")
            else:
                raise commands.BadArgument("Command not found.")

    @app_commands.guilds(cfg.guild_id)
    @app_commands.command(description="View usage of a command")
    @app_commands.describe(command_name="The name of the command to get info of")
    @app_commands.autocomplete(command_name=command_list_autocomplete)
    @transform_context
    @whisper
    async def usage(self, ctx: BlooContext, command_name: str):
        command_arg_split = command_name.split()
        if len(command_arg_split) > 1:
            # TODO fix this
            main_command: app_commands.Group = self.bot.tree.get_command(command_arg_split[0].lower(), guild=ctx.guild)
            # sub_commands = [sc for sc in main_command.subcommands if command_name.lower() in f"{main_command.name} {sc.name}"]
            # if not sub_commands:
            #     raise commands.BadArgument("Command not found.")
            command = main_command.get_command(command_arg_split[1].lower())
            if not command:
                raise commands.BadArgument("Command not found.")

        else:
            command = self.bot.tree.get_command(command_name.lower(), guild=ctx.guild)
            if not command:
                raise commands.BadArgument("Command not found.")

        embed = await self.get_usage_embed(ctx, command)
        await ctx.respond(embed=embed, ephemeral=ctx.whisper)

    async def get_usage_embed(self,  ctx: BlooContext, command: app_commands.Command) -> discord.Embed:
        if command.binding.qualified_name in self.mod_only and not gatekeeper.has(ctx.guild, ctx.author, 5):
            raise commands.BadArgument("You don't have permission to view that command.")
        elif command.binding.qualified_name in self.genius_only and not gatekeeper.has(ctx.guild, ctx.author, 4):
            raise commands.BadArgument("You don't have permission to view that command.")
        else:
            args = ""
            for name, arg in command._params.items():
                if not arg.required:
                    args += f"[{name}] "
                else:
                    args += f"<{name}> "

            if command.parent is not None:
                embed = discord.Embed(title=f"/{command.parent.name} {command.name} {args}")
            else:
                embed = discord.Embed(title=f"/{command.name} {args}")
            
            embed.description = f"{command.description or 'No description.'}\n```hs\n"
            for name, option in command._params.items():
                embed.description += f"{name}: {str(option.type).split('.')[1]}{', optional' if not option.required else ''}\n    \"{option.description}\"\n"
                
            embed.description += "```"
            embed.color = discord.Color.random()
            return embed


async def setup(bot):
    await bot.add_cog(Utilities(bot))
