#!/usr/bin/env python3
"""
SOCA Weather Bot — 台北每日天氣推播
資料來源：Open-Meteo (https://open-meteo.com/)
推播：Telegram Bot API
排程：cron 每天 08:30 (Asia/Taipei)

獨立腳本，與 OpenClaw / SOCA 主 bot 完全分離。
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from quote_picker import pick_and_format

# ── 設定 ──────────────────────────────────────────────────────────────
HOME = Path.home()
SECRETS_DIR = HOME / ".openclaw" / "secrets"
TOKEN_FILE = SECRETS_DIR / "weather_bot_token"
CHAT_ID_FILE = SECRETS_DIR / "weather_bot_chat_id"

PROJECT_DIR = Path(__file__).resolve().parent
QUOTES_FILE = PROJECT_DIR / "quotes.json"
QUOTE_STATE_FILE = HOME / ".openclaw" / "state" / "weather_bot_quote_state.json"

LOG_DIR = HOME / "projects" / "soca-weather-bot" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 台北 101 周邊座標（信義區），代表台北市區
LAT = 25.0330
LON = 121.5654
TZ = "Asia/Taipei"
TPE = timezone(timedelta(hours=8))

OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&daily=temperature_2m_max,temperature_2m_min,sunset,"
    "precipitation_sum,precipitation_probability_max,weather_code"
    "&hourly=temperature_2m,precipitation_probability,weather_code"
    f"&timezone={urllib.parse.quote(TZ)}"
    "&forecast_days=1"
)

# WMO weather code → (描述, emoji)
# 參考: https://open-meteo.com/en/docs (WMO Weather interpretation codes)
WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("晴朗", "☀️"),
    1: ("大致晴朗", "🌤️"),
    2: ("局部多雲", "⛅"),
    3: ("陰天", "☁️"),
    45: ("有霧", "🌫️"),
    48: ("凍霧", "🌫️"),
    51: ("毛毛雨", "🌦️"),
    53: ("中度毛毛雨", "🌦️"),
    55: ("濃毛毛雨", "🌦️"),
    56: ("凍毛毛雨", "🌧️"),
    57: ("濃凍毛毛雨", "🌧️"),
    61: ("小雨", "🌧️"),
    63: ("中雨", "🌧️"),
    65: ("大雨", "🌧️"),
    66: ("凍雨", "🌧️❄️"),
    67: ("強凍雨", "🌧️❄️"),
    71: ("小雪", "🌨️"),
    73: ("中雪", "🌨️"),
    75: ("大雪", "🌨️"),
    77: ("雪粒", "🌨️"),
    80: ("陣雨", "🌦️"),
    81: ("中陣雨", "🌧️"),
    82: ("強陣雨", "⛈️"),
    85: ("陣雪", "🌨️"),
    86: ("強陣雪", "🌨️"),
    95: ("雷雨", "⛈️"),
    96: ("雷雨夾冰雹", "⛈️"),
    99: ("強雷雨夾冰雹", "⛈️"),
}


# ── Logging ──────────────────────────────────────────────────────────
log_file = LOG_DIR / f"{datetime.now(TPE).strftime('%Y-%m')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("weather-bot")


# ── 工具函式 ─────────────────────────────────────────────────────────
def read_secret(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Secret not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def http_get_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "SOCA-Weather-Bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url: str, data: dict, timeout: int = 15) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SOCA-Weather-Bot/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def describe_weather(code: int) -> tuple[str, str]:
    return WEATHER_CODES.get(code, ("天氣狀況不明", "🌡️"))


# ── 取得日落時刻氣溫 ─────────────────────────────────────────────────
def temp_at(hourly_times: list[str], hourly_temps: list[float], target_iso: str) -> float | None:
    """
    從 hourly 資料找最接近 target_iso（YYYY-MM-DDTHH:MM）的氣溫。
    """
    target_dt = datetime.fromisoformat(target_iso)
    best_idx = None
    best_diff = None
    for i, t in enumerate(hourly_times):
        diff = abs((datetime.fromisoformat(t) - target_dt).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_idx = i
    if best_idx is None:
        return None
    return hourly_temps[best_idx]


# ── 主播稿 ───────────────────────────────────────────────────────────
def build_broadcast(data: dict) -> str:
    daily = data["daily"]
    hourly = data["hourly"]

    today_iso = daily["time"][0]
    t_max = daily["temperature_2m_max"][0]
    t_min = daily["temperature_2m_min"][0]
    sunset_iso = daily["sunset"][0]  # e.g. 2026-05-04T18:25
    pop_max = daily["precipitation_probability_max"][0]
    rain_sum = daily["precipitation_sum"][0]
    code = daily["weather_code"][0]

    desc, emoji = describe_weather(code)

    sunset_temp = temp_at(hourly["time"], hourly["temperature_2m"], sunset_iso)
    sunset_hhmm = datetime.fromisoformat(sunset_iso).strftime("%H:%M")

    today_dt = datetime.fromisoformat(today_iso)
    weekday_zh = ["一", "二", "三", "四", "五", "六", "日"][today_dt.weekday()]
    date_str = today_dt.strftime(f"%-m月%-d日（週{weekday_zh}）")

    # 主播口吻
    lines = []
    lines.append(f"<b>☀️ 台北今日天氣 — {date_str}</b>")
    lines.append("")
    lines.append(f"早安！今天台北{emoji} <b>{desc}</b>。")
    lines.append("")
    lines.append(f"🔆 白天最高溫 <b>{t_max:.1f}°C</b>")
    if sunset_temp is not None:
        lines.append(f"🌅 黃昏（{sunset_hhmm} 日落）約 <b>{sunset_temp:.1f}°C</b>")
    else:
        lines.append(f"🌅 日落時間 {sunset_hhmm}")
    lines.append(f"❄️ 入夜後低溫 <b>{t_min:.1f}°C</b>")
    lines.append("")

    # 降雨提示
    if pop_max is None:
        pop_text = "—"
    else:
        pop_text = f"{int(pop_max)}%"

    if rain_sum is None or rain_sum < 0.05:
        if pop_max and pop_max >= 60:
            lines.append(f"🌧️ 降雨機率 {pop_text}，雖然雨量不大，出門帶把傘比較安心。")
        elif pop_max and pop_max >= 30:
            lines.append(f"🌦️ 降雨機率 {pop_text}，可能會飄點雨，留意一下天色。")
        else:
            lines.append(f"☂️ 降雨機率 {pop_text}，今天大致不必擔心下雨。")
    else:
        rain_str = f"{rain_sum:.1f} mm"
        if rain_sum >= 10:
            lines.append(f"🌧️ 降雨機率 {pop_text}，預估雨量 {rain_str}，雨勢不小，請務必攜帶雨具。")
        elif rain_sum >= 1:
            lines.append(f"🌧️ 降雨機率 {pop_text}，預估雨量 {rain_str}，記得帶傘。")
        else:
            lines.append(f"🌦️ 降雨機率 {pop_text}，預估雨量 {rain_str}，可能會有零星短暫雨。")

    # 結尾
    diff = t_max - t_min
    if diff >= 10:
        lines.append("")
        lines.append(f"📈 日夜溫差大（約 {diff:.1f}°C），出門記得多帶一件外套。")
    elif t_min <= 15:
        lines.append("")
        lines.append("🧥 清晨偏涼，注意保暖。")
    elif t_max >= 32:
        lines.append("")
        lines.append("💧 高溫炎熱，請多補充水分、避免長時間曝曬。")

    # 今日語錄(失敗就跳過,不影響天氣推播)
    try:
        quote_block = pick_and_format(QUOTES_FILE, QUOTE_STATE_FILE)
        lines.append("")
        lines.append("━━━━━━━━━━━━━━")
        lines.append("")
        lines.append(quote_block)
    except Exception as e:
        log.warning("產生語錄失敗(略過):%s", e)

    lines.append("")
    lines.append("祝你有美好的一天 🍊")

    return "\n".join(lines)


# ── 推播 ─────────────────────────────────────────────────────────────
def send_telegram(token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    return http_post_json(url, payload)


# ── main ─────────────────────────────────────────────────────────────
def main() -> int:
    log.info("=== SOCA Weather Bot 啟動 ===")
    try:
        token = read_secret(TOKEN_FILE)
        chat_id = read_secret(CHAT_ID_FILE)
    except FileNotFoundError as e:
        log.error("讀取 secret 失敗：%s", e)
        return 2

    try:
        log.info("呼叫 Open-Meteo API")
        data = http_get_json(OPEN_METEO_URL)
    except Exception as e:
        log.exception("Open-Meteo API 失敗：%s", e)
        # 失敗時仍然推一則簡短訊息，避免靜默失敗
        try:
            send_telegram(
                token,
                chat_id,
                f"⚠️ 今早天氣預報暫時拿不到（Open-Meteo API 失敗）。\n錯誤：<code>{type(e).__name__}: {e}</code>",
            )
        except Exception:
            log.exception("Telegram 失敗訊息也送不出去")
        return 3

    try:
        text = build_broadcast(data)
    except Exception as e:
        log.exception("產生播報內容失敗：%s", e)
        return 4

    log.info("送出 Telegram 訊息（%d chars）", len(text))
    try:
        resp = send_telegram(token, chat_id, text)
        if not resp.get("ok"):
            log.error("Telegram 回傳非 ok：%s", resp)
            return 5
        log.info("✅ 推播成功 message_id=%s", resp["result"].get("message_id"))
    except Exception as e:
        log.exception("Telegram 發送失敗：%s", e)
        return 6

    return 0


if __name__ == "__main__":
    sys.exit(main())
