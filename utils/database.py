import asyncio
# from io import BytesIO
import os
from beanie import init_beanie
from data.model import Guild
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from data.model.cases import Cases
from data.model.giveaway import Giveaway

from data.model.guild import Guild
from data.model.user import User
from .config import cfg
from .logging import logger

class Database:
    client: AsyncIOMotorClient
    fs: AsyncIOMotorGridFSBucket
    
    def __init__(self):
        logger.info("Starting database...")
        if os.environ.get("DB_CONNECTION_STRING") is None:
            self.client = AsyncIOMotorClient(f"mongodb://{os.environ.get('DB_HOST')}:{os.environ.get('DB_PORT')}")
        else:
            self.client = AsyncIOMotorClient(os.environ.get("DB_CONNECTION_STRING"))

    async def init_db(self):
        await init_beanie(database=self.client.botty, document_models=[Guild, User, Cases, Giveaway])
        self.fs = AsyncIOMotorGridFSBucket(self.client.botty)
        logger.info("Database connected and loaded successfully!")
        
        # guild = await Guild.find_one(Guild.id == cfg.guild_id)
        # # images = ([tag.image for tag in guild.tags if tag.image is not None])
        
        # with open('myfile.jpg','rb') as file:
        #     fs = AsyncIOMotorGridFSBucket(self.client.botty)
        #     tmp = BytesIO(file.read())
        #     uploaded = await fs.upload_from_stream(
        #         filename="my_file", source=tmp, metadata={"contentType": "image/jpeg"}
        #     )

        #     with open('myfile2.jpg','wb+') as file:
        #         fs = AsyncIOMotorGridFSBucket(self.client.botty)
        #         await fs.download_to_stream(uploaded, file)

        if not await Guild.find_one(Guild.id == cfg.guild_id):
            raise Exception(f"The database has not been set up for guild {cfg.guild_id}! Please refer to README.md.")


db = Database()
