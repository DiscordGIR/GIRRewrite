# imports
from dotenv.main import load_dotenv

import argparse
import logging
import os
import radium as r

load_dotenv()

class Logger:
    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--disable-discord-logs', help='Disables Discord logging.', action='store_true')
        parser.add_argument('--disable-scheduler-logs', help='Disables scheduler logs.', action='store_true')
        parser.add_argument('--disable-webhook-logging', help='Disables logging to the webhook.', action='store_true')
        args = parser.parse_args()

        wh = r.WebhookLogger(url=os.environ.get("LOGGING_WEBHOOK_URL"), ids_to_ping=[os.environ.get('OWNER_ID')])
        
        if not args.disable_discord_logs:
            discord_logger = logging.getLogger('discord')
            discord_logger.setLevel(logging.WARN)
            discord_logger.addHandler(r.Radium)
            if not args.disable_webhook_logging:
                discord_logger.addHandler(wh)
        if not args.disable_scheduler_logs:
            ap_logger = logging.getLogger('apscheduler')
            ap_logger.setLevel(logging.INFO)
            ap_logger.addHandler(r.Radium)
            if not args.disable_webhook_logging:
                ap_logger.addHandler(wh)
        self.logger = logging.Logger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(r.Radium)
        if not args.disable_webhook_logging:
            self.logger.addHandler(wh)

logger = Logger().logger
