from discord.ext import commands

"""
A custom Cooldown type subclassing built in cooldowns from discord.ext commands.
This is a bucket type that allows cooldowns to work based on some text, allowing
things like cooldown on individual `Tags`, or message spam detection.
"""

class MessageTextBucket(commands.BucketType):
    custom = 7
    
    def get_key(self, text):
        return text
        
    def __call__(self, msg):
        return self.get_key(msg)   
