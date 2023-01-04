import datetime
import random
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
import pytz
from data.model.battle import Battle
from utils import cfg, GIRContext, transform_context
from utils.framework import mod_and_up
from utils.framework.checks import always_whisper
from utils.views.menus.menu import Menu


def format_submission_page(ctx, entries, current_page, all_pages):
    embed = discord.Embed(title="Setup battle results", color=discord.Color.random())
    embed.description = ""

    for i, entry in entries:
        embed.description += f"{i+1}. {entry}\n\n"

    embed.set_footer(
        text=f"{ctx.total_votes} votes in total • Page {current_page} of {len(all_pages)}")
    return embed


class ViewSubmissionsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Click here to vote!", emoji='🗳️', style=discord.ButtonStyle.primary, custom_id="voteButton")
        self.min_join_date = datetime.datetime(2022, 12, 24, tzinfo=pytz.UTC)

    async def callback(self, interaction: discord.Interaction):
        clicker = interaction.user
        ctx = GIRContext(interaction)
        if clicker.joined_at > self.min_join_date:
            await ctx.send_error(description=f"Sorry, we're only accepting submissions from people that joined before {discord.utils.format_dt(self.min_join_date, style='D')}!", whisper=True)
            return

        previously_voted = Battle.objects(votes__contains=clicker.id)
        if previously_voted:
            await ctx.send_error(description="You've already voted!", whisper=True)
            return

        previously_viewed = Battle.objects(seen_by__contains=clicker.id)
        if previously_viewed:
            submissions = previously_viewed[:2]
        else:
            all_submissions = list(Battle.objects(_id__ne=clicker.id).all())
            submissions = random.sample(all_submissions, k=2)

            for submission in submissions:
                Battle.objects(_id=submission._id).update_one(push__seen_by=clicker.id)

        view = VoteView(clicker, submissions[0], submissions[1])
        await ctx.respond(f"1️⃣ {submissions[0].link}\n2️⃣ {submissions[1].link}", view=view, ephemeral=True)
        
        await view.wait()
        result = view.voted_value
        if result is None:
            await ctx.send_warning("Timed out waiting for your response! Feel free to click the button to vote again.")

        previously_voted = Battle.objects(votes__contains=clicker.id)
        if previously_voted:
            ctx.send_error(description="You've already voted!", whisper=True)
            return
        
        Battle.objects(_id=result._id).update_one(push__votes=clicker.id)
        await ctx.send_success("You've cast your vote. Thanks!", ephemeral=True)


class VoteView(discord.ui.View):
    submission_one: Battle
    submission_two: Battle
    voter: discord.Member
    voted_value: Optional[Battle]

    def __init__(self, voter: discord.Member, submission_one: Battle, submission_two: Battle):
        self.voter = voter
        self.submission_one = submission_one
        self.submission_two = submission_two
        super().__init__(timeout=120)

    @discord.ui.button(emoji='1️⃣', style=discord.ButtonStyle.primary)
    async def vote_one(self, interaction: discord.Interaction, _):
        self.voted_value = self.submission_one
        self.stop()
    
    @discord.ui.button(emoji='2️⃣', style=discord.ButtonStyle.primary)
    async def vote_two(self, interaction: discord.Interaction, _):
        self.voted_value = self.submission_two
        self.stop()

class SetupBattle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    submissions = app_commands.Group(
        name="submissions", description="Interact with setup battle submissions", guild_ids=[cfg.guild_id])

    @mod_and_up()
    @submissions.command(description="Add a new submission")
    @app_commands.describe(user="User that made the submission")
    @app_commands.describe(link="Link to the Imgur album with the submission")
    @transform_context
    @always_whisper
    async def add(self, ctx: GIRContext, user: discord.Member, link: str):
        if not link.startswith("https://"):
            raise commands.BadArgument("A valid URL was not provided for the link parameter.")

        user_db_object = Battle.objects(_id=user.id).first()
        if user_db_object is not None:
            raise commands.BadArgument("This user already has a submission!")

        user_db_object = Battle()
        user_db_object._id = user.id
        user_db_object.link = link
        user_db_object.save()

        await ctx.send_success(f"Added new submission from {user.mention}!")

    @mod_and_up()
    @submissions.command(description="Remove an existing submission")
    @app_commands.describe(user="User that made the submission")
    @transform_context
    @always_whisper
    async def remove(self, ctx: GIRContext, user: discord.Member):
        user_db_object = Battle.objects(_id=user.id).first()
        if user_db_object is None:
            raise commands.BadArgument("This user hasn't submitted anything!")

        Battle.objects(_id=user.id).delete()
        await ctx.send_success("Submission was deleted!")

    @mod_and_up()
    @submissions.command(description="View results")
    @transform_context
    @always_whisper
    async def results(self, ctx: GIRContext):
        submissions = list(Battle.objects().all())
        total_vote_count = sum([len(submission.votes) for submission in submissions])
        submissions.sort(key=lambda x: len(x.votes), reverse=True)
        submission_strings = []
    
        for submission in submissions:
            if total_vote_count == 0:
                vote_percent = 0
            else:
                vote_percent = (len(submission.votes) / total_vote_count) * 100

            percent_rounded = round(vote_percent/10)
            string = f"<@{submission._id}> ([link]({submission.link})): {len(submission.votes)} votes\n{'🟩' * percent_rounded}{'⬛' * (10 - percent_rounded)} ({vote_percent}%)"
            submission_strings.append(string)
        
        submission_strings = list(enumerate(submission_strings))
        ctx.total_votes = total_vote_count
        
        menu = Menu(ctx, submission_strings, per_page=10,
                    page_formatter=format_submission_page, whisper=True)
        await menu.start()

    @mod_and_up()
    @submissions.command(description="Post the message users can click on to vote")
    @transform_context
    async def postembed(self, ctx: GIRContext):
        embed = discord.Embed(color=discord.Color.blurple(), title="How voting works", description="You will be given 2 submissions to choose from. These 2 are randomly picked by the bot and its your job to vote for the better one. The submission with the most votes at the end of the voting period wins.\n\nWhy? Because there are 20+ submissions and looking through each one is impractical.\n\nClick on the button below to see the submissions you can vote on!")
        embed.set_footer(text="Note: You can only vote once.")

        view = discord.ui.View(timeout=None)
        view.add_item(ViewSubmissionsButton())
        
        await ctx.channel.send(embed=embed, view=view)
        await ctx.send_success("Done!", ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        view = discord.ui.View(timeout=None)
        view.add_item(ViewSubmissionsButton())

        self.bot.add_view(view)

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupBattle(bot))
