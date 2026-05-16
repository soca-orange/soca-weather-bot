#!/usr/bin/env python3
"""
SOCA Weather Bot Scheduler
自己計算下次推播時間並 sleep，完全不依賴 launchd StartCalendarInterval。
由 launchd KeepAlive 保持永久存活。
"""

import subprocess
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

TPE = timezone(timedelta(hours=8))
SCRIPT = Path(__file__).resolve().parent / "weather_bot.py"
PYTHON = sys.executable

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scheduler.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("scheduler")

# (hour, minute, mode)
SCHEDULE = [
    (8, 30, "morning"),
    (23, 30, "evening"),
]


def seconds_until(hour: int, minute: int) -> float:
    now = datetime.now(TPE)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def next_target() -> tuple[float, str]:
    options = [(seconds_until(h, m), mode) for h, m, mode in SCHEDULE]
    options.sort()
    return options[0]


def main():
    log.info("=== SOCA Scheduler 啟動 ===")
    while True:
        wait_secs, mode = next_target()
        h = int(wait_secs // 3600)
        m = int((wait_secs % 3600) // 60)
        log.info("下次推播：%s，等待 %dh%dm (%.0fs)", mode, h, m, wait_secs)
        time.sleep(wait_secs)

        now_str = datetime.now(TPE).strftime("%H:%M")
        log.info("時間到，執行 weather_bot.py --mode %s (現在 %s)", mode, now_str)
        result = subprocess.run(
            [PYTHON, str(SCRIPT), "--mode", mode],
            timeout=120,
        )
        if result.returncode != 0:
            log.error("weather_bot.py 退出碼 %d", result.returncode)


if __name__ == "__main__":
    main()
