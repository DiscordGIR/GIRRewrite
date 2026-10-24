"""Discord readiness heartbeat; also executable by Docker without importing config."""

import asyncio
import os
from pathlib import Path
import time


async def report_health(bot, path):
    marker = Path(path)
    marker.unlink(missing_ok=True)
    try:
        while True:
            if bot.is_ready() and bot.deployment_ready:
                marker.write_text(str(time.monotonic()), encoding="ascii")
            else:
                marker.unlink(missing_ok=True)
            await asyncio.sleep(5)
    finally:
        marker.unlink(missing_ok=True)


def healthy(path):
    try:
        age = time.monotonic() - float(Path(path).read_text(encoding="ascii"))
        return 0 <= age < 30
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    raise SystemExit(0 if healthy(os.environ.get("GIR_HEALTH_FILE", "/tmp/gir-ready")) else 1)
