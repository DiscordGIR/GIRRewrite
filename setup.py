import asyncio
import os

import mongoengine
from dotenv import find_dotenv, load_dotenv

from data.model.guild import Guild

load_dotenv(find_dotenv())

async def setup():
    print("STARTING SETUP...")
    guild = Guild()

    # you should have this setup in the .env file beforehand
    guild._id          = int(os.environ.get("MAIN_GUILD_ID"))

    # If you're re-running this script to update a value, set case_id
    # to the last unused case ID or else it will start over from 1!
    guild.case_id      = 1

    # you can fill these in if you want with IDs, or you ca use commands later
    guild.logging_excluded_channels = []  # put in a channel if you want (ignored in logging)
    guild.filter_excluded_channels  = []  # put in a channel if you want (ignored in filter)
    guild.filter_excluded_guilds    = []  # put guild ID to whitelist in invite filter if you want

    guild.nsa_guild_id = 123 # you can leave this as is if you don't want Blootooth (message mirroring system)

    guild.save()
    print("DONE")

if __name__ == "__main__":
    if os.environ.get("DB_CONNECTION_STRING") is None:
        mongoengine.register_connection(
            host=os.environ.get("DB_HOST"), port=int(os.environ.get("DB_PORT")), alias="default", name="botty")
    else:
        mongoengine.register_connection(
            host=os.environ.get("DB_CONNECTION_STRING"), alias="default", name="botty")
    res = asyncio.get_event_loop().run_until_complete( setup() )
