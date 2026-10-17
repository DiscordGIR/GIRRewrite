"""Load every extension without credentials, a gateway connection, or MongoDB."""
import asyncio
import os
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

import mongoengine
import mongomock
from apscheduler.jobstores.memory import MemoryJobStore

from data.model import Guild


async def check():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        shutil.copy(root / "config.example.json", Path(directory) / "config.json")
        shutil.copy(root / "emojis.json", Path(directory) / "emojis.json")
        os.chdir(directory)
        os.environ.clear()
        os.environ.update(MAIN_GUILD_ID="123", OWNER_ID="123", AARON_ID="123",
                          DB_HOST="localhost", DB_PORT="27017")
        mongoengine.connect("botty", mongo_client_class=mongomock.MongoClient)
        Guild(_id=123, case_id=1).save()
        with patch("dotenv.main.load_dotenv"), patch("mongoengine.register_connection"):
            import main
            import utils.jobs
            with patch.object(utils.jobs, "MongoDBJobStore", side_effect=lambda **kwargs: MemoryJobStore()):
                async with main.bot:
                    await main.bot.setup_hook()
                    assert set(main.bot.extensions) == set(main.initial_extensions)
                    assert main.bot.get_cog("AntiRaidMonitor") is not None
                    assert main.bot.tasks.tasks.state == 2  # paused until Discord is ready
        assert main.bot.is_closed()
        mongoengine.disconnect()


if __name__ == "__main__":
    asyncio.run(check())
