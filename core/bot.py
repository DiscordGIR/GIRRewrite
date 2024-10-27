from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncEngine

from core.database import get_engine
from extensions import initial_extensions
from utils import BanCache, IssueCache, RuleCache, Tasks, cfg, db, logger, init_client_session
from utils.framework import gatekeeper


class Bot(commands.Bot):
    engine: AsyncEngine
    ban_cache: BanCache
    issue_cache: IssueCache
    rule_cache: RuleCache
    tasks: Tasks

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ban_cache = BanCache(self)
        self.issue_cache = IssueCache(self)
        self.rule_cache = RuleCache(self)
        self.engine = get_engine()

        # force the config object and database connection to be loaded
        if cfg and db and gatekeeper:
            logger.info("Presetup phase completed! Connecting to Discord...")

    async def setup_hook(self):
        self.remove_command("help")
        for extension in initial_extensions:
            await self.load_extension(extension)

        from cogs.commands.context_commands import setup_context_commands
        setup_context_commands(self)

        self.tasks = Tasks(self)
        await init_client_session()
