"""
名言佳句挑選器
- 從 quotes.json 隨機挑一則
- 用 state 檔記錄最近挑過的索引,避免短期重複
- 純標準庫實作
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

log = logging.getLogger("weather-bot.quotes")

# 語言標籤 → 顯示名稱
LANG_LABEL = {
    "zh-classical": "古文",
    "zh-modern": "中文",
    "en": "English",
    "ja": "日本語",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
    "la": "Latin",
    "grc": "Ἑλληνική",
}


def load_quotes(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        quotes = json.load(f)
    if not isinstance(quotes, list) or not quotes:
        raise ValueError(f"quotes file empty or malformed: {path}")
    return quotes


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"recent": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("讀取 quote state 失敗,重設:%s", e)
        return {"recent": []}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_quote(quotes: list[dict], state: dict, avoid_last: int = 15) -> tuple[int, dict]:
    """
    從 quotes 隨機挑一則,避免最近 avoid_last 則。
    回傳 (index, quote)。
    """
    n = len(quotes)
    avoid = set(state.get("recent", [])[-avoid_last:])
    candidates = [i for i in range(n) if i not in avoid]
    # 全部都被 avoid 的話(quotes 太少 / avoid_last 太大),就放寬限制
    if not candidates:
        candidates = list(range(n))
    idx = random.choice(candidates)
    return idx, quotes[idx]


def format_quote(q: dict) -> str:
    """
    產生 Telegram HTML 格式的語錄區塊。
    - 中文(古文/現代)→ 翻譯不必再寫,顯示原文 + (古文時)附白話
    - 其他語言 → 原文 + 中文白話
    """
    lang = q.get("lang", "")
    original = q["original"]
    translation = q.get("translation", "—")
    author = q.get("author", "佚名")
    source = q.get("source", "")
    label = LANG_LABEL.get(lang, lang or "—")

    lines = []
    lines.append("✨ <b>今日語錄</b>")
    lines.append("")

    if lang == "zh-modern":
        # 現代中文,直接呈現原文
        lines.append(f"<i>「{original}」</i>")
    elif lang == "zh-classical":
        # 古文：原文 + 白話翻譯
        lines.append(f"<i>「{original}」</i>")
        if translation and translation != "—":
            lines.append(f"<blockquote>白話:{translation}</blockquote>")
    else:
        # 外文:中文白話翻譯先,原文補後
        lines.append(f"<i>「{translation}」</i>")
        if original:
            lines.append(f"<blockquote>{label} 原文:{original}</blockquote>")

    # 作者 + 出處
    attribution = f"— {author}"
    if source and source != "（傳統諺語）":
        attribution += f"，{source}"
    elif source:
        attribution += f"（{source.strip('（）')}）"
    lines.append(attribution)

    return "\n".join(lines)


def pick_and_format(quotes_path: Path, state_path: Path, avoid_last: int = 15) -> str:
    """
    完整流程:挑一則、更新 state、回傳格式化字串。
    """
    quotes = load_quotes(quotes_path)
    state = load_state(state_path)
    idx, quote = pick_quote(quotes, state, avoid_last=avoid_last)
    log.info("選中語錄 idx=%d lang=%s author=%s", idx, quote.get("lang"), quote.get("author"))

    # 更新 recent (保留最後 avoid_last * 2 則,夠避免重複又不無限長)
    recent = state.get("recent", [])
    recent.append(idx)
    state["recent"] = recent[-(avoid_last * 2):]
    try:
        save_state(state_path, state)
    except Exception as e:
        log.warning("寫入 quote state 失敗(不影響推播):%s", e)

    return format_quote(quote)
