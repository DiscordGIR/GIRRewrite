from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncEngine

from core.database import get_engine
from core.extensions import initial_extensions
from utils import cfg, db, logger, BanCache, IssueCache, Tasks, RuleCache, init_client_session
from utils.framework import gatekeeper


class Bot(commands.Bot):
    engine: AsyncEngine
    ban_cache: BanCache
    issue_cache: IssueCache
    rule_cache: RuleCache
    tasks: Tasks

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.engine = get_engine()

        self.ban_cache = BanCache(self)
        self.issue_cache = IssueCache(self)
        self.rule_cache = RuleCache(self)

        # force the config object and database connection to be loaded
        if cfg and db and gatekeeper and self.engine:
            logger.info("Presetup phase completed! Connecting to Discord...")

    async def setup_hook(self):
        self.remove_command("help")
        for extension in initial_extensions:
            await self.load_extension(extension)

        self.tasks = Tasks(self)
        await init_client_session()


