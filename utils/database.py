import asyncio
import gzip
from io import BytesIO
import os
import tempfile
from beanie import init_beanie
# import mongoengine
# from data.model import Guild
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

from data.model.guild import Guild
from .config import cfg
from .logging import logger

class Database:
    client: AsyncIOMotorClient
    
    def __init__(self):
        logger.info("Starting database...")
        if os.environ.get("DB_CONNECTION_STRING") is None:
            # mongoengine.register_connection(
            #     host=os.environ.get("DB_HOST"), port=int(os.environ.get("DB_PORT")), alias="default", name="botty")
            self.client = AsyncIOMotorClient(f"mongodb://{os.environ.get('DB_HOST')}:{os.environ.get('DB_PORT')}")
        else:
            self.client = AsyncIOMotorClient(os.environ.get("DB_CONNECTION_STRING"))
            
        asyncio.run(self.init_db())
        
    async def init_db(self):
        await init_beanie(database=self.client.botty, document_models=[Guild])
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

        # if not Guild.objects(_id=cfg.guild_id):
        #     raise Exception(f"The database has not been set up for guild {cfg.guild_id}! Please refer to README.md.")


db = Database()
