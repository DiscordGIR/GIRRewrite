import argparse
import asyncio
import logging
import os
import sys

import aiohttp
import discord
from dotenv.main import load_dotenv

load_dotenv()

class Formatter(logging.Formatter):
    def __init__(self):
        self.style_list = {
            'bright': '\x1b[1m',
            'dim': '\x1b[2m',
            'underscore': '\x1b[4m',
            'blink': '\x1b[5m',
            'reverse': '\x1b[7m',
            'hidden': '\x1b[8m',
            'black': '\x1b[30m',
            'red': '\x1b[31m',
            'green': '\x1b[32m',
            'yellow': '\x1b[33m',
            'blue': '\x1b[34m',
            'magenta': '\x1b[35m',
            'reset': '\x1b[0m',
            'cyan': '\x1b[36m',
            'white': '\x1b[37m',
            'bgBlack': '\x1b[40m',
            'bgRed': '\x1b[41m',
            'bgGreen': '\x1b[42m',
            'bgYellow': '\x1b[43m',
            'bgBlue': '\x1b[44m',
            'bgMagenta': '\x1b[45m',
            'bgCyan': '\x1b[46m',
            'bgWhite': '\x1b[47m'
        }
        self.err_fmt = f"{self.style_list.get('dim')}[{self.style_list.get('reset')}{self.style_list.get('red')}!{self.style_list.get('reset')}{self.style_list.get('dim')}]{self.style_list.get('reset')} %(message)s"
        self.dbg_fmt = f"{self.style_list.get('dim')}[{self.style_list.get('reset')}{self.style_list.get('yellow')}#{self.style_list.get('reset')}{self.style_list.get('dim')}]{self.style_list.get('reset')} (m:'%(module)s', l:%(lineno)s) %(message)s"
        self.warn_fmt = f"{self.style_list.get('dim')}[{self.style_list.get('reset')}{self.style_list.get('yellow')}?{self.style_list.get('reset')}{self.style_list.get('dim')}]{self.style_list.get('reset')} (m:'%(module)s', l:%(lineno)s) %(message)s"
        self.info_fmt = f"{self.style_list.get('dim')}[{self.style_list.get('reset')}{self.style_list.get('green')}*{self.style_list.get('reset')}{self.style_list.get('dim')}]{self.style_list.get('reset')} %(message)s"

        super().__init__(fmt=self.info_fmt, datefmt=None, style='%')

    def format(self, record):
        format_orig = self._style._fmt

        if record.levelname == 'DEBUG':
            self._style._fmt = self.dbg_fmt
        if record.levelname == 'ingo':
            self._style._fmt = self.info_fmt
        if record.levelname == 'WARNING':
            self._style._fmt = self.warn_fmt
        if record.levelname == 'ERROR':
            self._style._fmt = self.err_fmt

        result = logging.Formatter.format(self, record)

        self._style._fmt = format_orig

        return result


class WebhookLogger(logging.Handler):
    def __init__(self):
        self.level = logging.INFO
        super().__init__(self.level)
        self.webhook_url = os.environ.get("LOGGING_WEBHOOK_URL")
        self.record_formatter = logging.Formatter()
        
    def prefixcalc(self, levelname: str):
        if levelname == 'DEBUG':
            return '```bash#| '
        elif levelname == 'INFO':
            return '```diff\n+  | '
        elif levelname == 'WARNING':
            return '```css\n[  | '
        elif levelname == 'ERROR':
            return '```diff\n-!  | '
        elif levelname == 'CRITICAL':
            return '```diff\n-!!  | '
        else:
            return '```  |'

    def suffixcalc(self, levelname: str):
        if levelname == 'DEBUG':
            return '  ]```'
        elif levelname == 'WARNING':
            return '  ]```'
        else:
            return '```'

    def emit(self, record: logging.LogRecord):
        self.send(self.record_formatter.format(record), record)
            
    def send(self, formatted, record):
        if self.webhook_url is None:
            return

        parts = [formatted[i:i+1900] for i in range(0, len(formatted), 1900)]
        for i, part in enumerate(parts):
            content = f"{self.prefixcalc(record.levelname)}{part}{self.suffixcalc(record.levelname)}"
            if i == len(parts) - 1:
                if record.levelname == 'ERROR' or record.levelname == 'CRITICAL':
                    content += f'<@{os.environ.get("OWNER_ID")}>'
            message_body = {
                "content": content
            }

            try:
                loop = asyncio.get_event_loop()
                asyncio.ensure_future(post_content(self.webhook_url, message_body))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(post_content(self.webhook_url, message_body))

async def post_content(webhook_url, message_body):
    async with aiohttp.ClientSession() as session:
        the_webhook: discord.Webhook = discord.Webhook.from_url(webhook_url, session=session)
        try:
            await the_webhook.send(**message_body)
        except Exception:
            pass

class Logger:
    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--disable-discord-logs', help='Disables Discord logging.', action='store_true')
        parser.add_argument('--disable-scheduler-logs', help='Disables scheduler logs.', action='store_true')
        parser.add_argument('--disable-webhook-logging', help='Disables logging to the webhook.', action='store_true')

        args = parser.parse_args()

        self.HNDLR = logging.StreamHandler(sys.stdout)
        self.HNDLR.formatter = Formatter()
        if not args.disable_discord_logs:
            discord_logger = logging.getLogger('discord')
            discord_logger.setLevel(logging.INFO)
            discord_logger.addHandler(self.HNDLR)
            if not args.disable_webhook_logging:
                discord_logger.addHandler(WebhookLogger())
        if not args.disable_scheduler_logs:
            ap_logger = logging.getLogger('apscheduler')
            ap_logger.setLevel(logging.INFO)
            ap_logger.addHandler(self.HNDLR)
            if not args.disable_webhook_logging:
                ap_logger.addHandler(WebhookLogger())
        self.logger = logging.Logger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.HNDLR)
        if not args.disable_webhook_logging:
            self.logger.addHandler(WebhookLogger())
        
logger = Logger().logger
