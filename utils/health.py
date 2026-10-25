"""Low-overhead runtime measurements emitted once per minute."""
import asyncio
import time

import psutil


async def monitor_runtime(bot, logger):
    process = psutil.Process()
    samples = []
    while True:
        started = time.monotonic()
        await asyncio.sleep(1)
        samples.append(max(0, time.monotonic() - started - 1) * 1000)
        if len(samples) < 60:
            continue
        ordered = sorted(samples)
        antiraid = bot.get_cog("AntiRaidMonitor")
        logger.info(
            "runtime loop_lag_p95_ms=%.1f loop_lag_max_ms=%.1f rss_mib=%.1f "
            "db_operations=%s db_worker_seconds=%.2f image_queue=%s image_skipped=%s",
            ordered[int(len(ordered) * .95) - 1], ordered[-1],
            process.memory_info().rss / (1024 * 1024),
            bot.database_io.completed, bot.database_io.total_seconds,
            antiraid.image_queue.qsize() if antiraid else 0,
            antiraid.image_scans_dropped if antiraid else 0,
        )
        samples.clear()
