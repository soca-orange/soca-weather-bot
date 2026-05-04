# SOCA Weather Bot 🌤️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

每天 08:30（台北時間）自動推播台北天氣到 Telegram。

> 由 [SOCA](https://github.com/soca-orange) 🍊（Samuel's OpenClaw Assistant）建立並維護。

## 架構

完全獨立於 OpenClaw / SOCA 主 bot：

- **資料來源**：[Open-Meteo API](https://open-meteo.com/)（免費、無需 API key）
- **推播**：獨立 Telegram Bot `@SOCAWeatherBot`
- **排程**：macOS launchd（`~/Library/LaunchAgents/com.soca.weather-bot.plist`）
- **語言**：純 Python 3 標準函式庫，無第三方依賴

## 檔案

```
~/projects/soca-weather-bot/
├── weather_bot.py        # 主腳本
├── README.md             # 本檔
└── logs/
    ├── YYYY-MM.log       # 應用層日誌
    ├── launchd.out.log   # stdout
    └── launchd.err.log   # stderr

~/.openclaw/secrets/
├── weather_bot_token     # Telegram bot token (mode 600)
└── weather_bot_chat_id   # 推播目標 chat_id (mode 600)

~/Library/LaunchAgents/
└── com.soca.weather-bot.plist
```

## 維運指令

```bash
# 手動執行一次
python3 ~/projects/soca-weather-bot/weather_bot.py

# 查看最近日誌
tail -f ~/projects/soca-weather-bot/logs/$(date +%Y-%m).log

# 確認排程狀態
launchctl list | grep weather-bot
launchctl print gui/$(id -u)/com.soca.weather-bot

# 立即觸發（測試）
launchctl start com.soca.weather-bot

# 暫停 / 恢復
launchctl unload ~/Library/LaunchAgents/com.soca.weather-bot.plist
launchctl load ~/Library/LaunchAgents/com.soca.weather-bot.plist

# 修改執行時間
# → 編輯 plist 裡的 StartCalendarInterval，然後 unload + load
```

## 內容欄位

每日播報包含：

- 🔆 白天最高溫
- 🌅 黃昏（日落時）氣溫
- ❄️ 入夜後最低溫
- 🌧️ 降雨機率與預估雨量
- 📈 額外提示（溫差大、低溫保暖、高溫補水）
- ✨ 今日語錄：多語言名言佳句（中、英、日、法、德、西、拉丁、古希臘、古文）——原文 + 中文白話翻譯

## 語錄庫

語錄存在 [`quotes.json`](./quotes.json)，可以自由增刪。每則語錄的 schema：

```json
{
  "lang": "en | zh-classical | zh-modern | ja | fr | de | es | la | grc",
  "original": "原文",
  "translation": "中文白話翻譯（現代中文可以填 '—'）",
  "author": "作者",
  "source": "出處"
}
```

避免短期重複的 state 檔存在 `~/.openclaw/state/weather_bot_quote_state.json`。

## 失敗處理

- API 失敗時推播一則錯誤摘要訊息，避免靜默失敗
- 所有錯誤寫入 `logs/YYYY-MM.log`

## Setup（從零開始）

如果你想自己跑一份：

1. **建立你自己的 Telegram bot**：跟 [@BotFather](https://t.me/BotFather) 說 `/newbot`，拿到 token。
2. **取得 chat_id**：找你的 bot 開始對話，然後
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   裡面的 `chat.id` 就是。
3. **存 secrets**：
   ```bash
   mkdir -p ~/.openclaw/secrets
   echo "<TOKEN>" > ~/.openclaw/secrets/weather_bot_token
   echo "<CHAT_ID>" > ~/.openclaw/secrets/weather_bot_chat_id
   chmod 600 ~/.openclaw/secrets/weather_bot_*
   ```
4. **clone 專案**：
   ```bash
   git clone https://github.com/soca-orange/soca-weather-bot.git ~/projects/soca-weather-bot
   ```
5. **手動測試**：
   ```bash
   python3 ~/projects/soca-weather-bot/weather_bot.py
   ```
6. **設排程**（macOS）：複製 `com.soca.weather-bot.plist.example` 到 `~/Library/LaunchAgents/com.soca.weather-bot.plist`，把路徑改成你的，然後 `launchctl load`。

座標預設台北 101 周邊。要改地點，編輯 `weather_bot.py` 開頭的 `LAT` / `LON` / `TZ`。

## 注意：macOS 排程要記得讓機器醒著

`launchd` 在睡眠錯過排程**不會補跑**。建議搭配：

- `pmset -c sleep 0` 或 `caffeinate -i` 包裝程序
- `pmset repeat wake HH:MM` 作為 RTC 喚醒備案

（吃過這個虧 😅）

## License

MIT — see [LICENSE](./LICENSE).
