import os
import mongoengine
from data.model import Guild
from .config import cfg
from .logging import logger

class Database:
    def __init__(self):
        logger.info("Starting database...")
        if os.environ.get("DB_CONNECTION_STRING") is None:
            mongoengine.register_connection(
                host=os.environ.get("DB_HOST"), port=int(os.environ.get("DB_PORT")), alias="default", name="botty")
        else:
            mongoengine.register_connection(
                host=os.environ.get("DB_CONNECTION_STRING"), alias="default", name="botty")
        logger.info("Database connected and loaded successfully!")
        
        if not Guild.objects(_id=cfg.guild_id):
            raise Exception(f"The database has not been set up for guild {cfg.guild_id}! Please refer to README.md.")


db = Database()
