from discord.ext import commands
from utils.config import cfg

class AppleNews(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, msg):
        """When a message is posted in the #apple-news news channel, automatically publish it."""
        
        if not msg.guild:
            return
        if msg.channel.id != cfg.channels.applenews:
            return
        if not msg.author.bot:
            return
        if not msg.channel.is_news():
            return
        
        await msg.publish()
    
async def setup(bot):
    await bot.add_cog(AppleNews(bot))
