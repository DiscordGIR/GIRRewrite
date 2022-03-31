import os
from dotenv.main import load_dotenv
from .logging import logger


class Config:
    def __init__(self):
        load_dotenv()

        self.guild_id = int(os.environ.get("MAIN_GUILD_ID"))
        self.owner_id = int(os.environ.get("OWNER_ID"))

        if self.guild_id is None:
            self.setup_error("MAIN_GUILD_ID")

        if self.owner_id is None:
            self.setup_error("OWNER_ID")

        self.aaron_id = os.environ.get("AARON_ID")
        if self.aaron_id is None:
            self.setup_error("AARON_ID")
        self.aaron_id = int(self.aaron_id)

        self.aaron_role = os.environ.get("AARON_ROLE")
        if self.aaron_role is not None:
            self.aaron_role = int(self.aaron_role)
        else:
            self.setup_warning("AARON_ROLE")

        if os.environ.get("BAN_APPEAL_GUILD_ID") is None or os.environ.get("BAN_APPEAL_MOD_ROLE") is None:
            logger.info("Ban appeals monitoring is DISABLED!")
            self.ban_appeal_guild_id = None
        else:
            self.ban_appeal_guild_id = int(
                os.environ.get("BAN_APPEAL_GUILD_ID"))

            if os.environ.get("BAN_APPEAL_MOD_ROLE") is None:
                self.setup_error("BAN_APPEAL_MOD_ROLE")

            if os.environ.get("BAN_APPEAL_URL") is None:
                self.setup_error("BAN_APPEAL_URL")

            self.ban_appeal_url = os.environ.get("BAN_APPEAL_URL")
            self.ban_appeal_mod_role = int(
                os.environ.get("BAN_APPEAL_MOD_ROLE"))

        if os.environ.get("LOGGING_WEBHOOK_URL") is not None:
            logger.info("Discord webhook logging is ENABLED!")
        else:
            logger.info("Discord webhook logging is DISABLED!")

        self.resnext_token = os.environ.get("RESNEXT_TOKEN")
        self.open_ai_token = os.environ.get("OPEN_AI_TOKEN")
        if self.open_ai_token is None:
            logger.warning("`/memegen aitext` will not be enabled.")

        self.markov_enabled = os.environ.get("MARKOV_ENABLED")
        if self.markov_enabled != "True":
            self.markov_enabled = None
            logger.warning("Markov is DISABLED! `/memegen text` features will not be enabled.")

        self.dev = os.environ.get("DEV") is not None

        logger.info(
            f"GIR will be running in: {self.guild_id} in \033[1m{'DEVELOPMENT' if self.dev else 'PRODUCTION'}\033[0m mode")
        logger.info(f"Bot owned by: {self.owner_id}")

    def setup_warning(self, k: str):
        logger.warn(
            '.env file does not have key {}. Some features may not function as intended.'.format(k))

    def setup_error(self, k: str):
        logger.error(
            '.env file is not correctly set up! Missing key {}'.format(k))
        exit(1)


cfg = Config()
