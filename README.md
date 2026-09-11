# 🌐 Telegram Multilingual Translator + Butler AI Bot

A complete, production-ready Telegram bot that acts as an **automatic multilingual translator and an intelligent, human-like AI Butler**.

---

## 🚀 Key Highlights & Philosophy

* **Zero Visible Commands:** Normal users never need to type `/translate`, `/tl`, or `/help`. Everything works naturally through regular conversation.
* **Uninhibited Slang & Profanity Preservation:** If a message contains street slang, vulgarity, or insults (Persian, Burmese, Hindi/Hinglish, etc.), the bot translates the exact emotional intensity and bite without moralizing, softening, or censoring.
* **Default State for New Groups:**
  * **Translator:** 🟢 **ON**
  * **Butler AI:** 🔴 **OFF** (The bot never randomly interrupts or chats unless enabled).
* **Invisible Owner Controls:**
  * `/enable` - Silently activates Butler AI for the group.
  * `/disable` - Silently deactivates Butler AI.
  * Verified strictly against `OWNER_IDS`. Unauthorized users attempting these commands are silently ignored with zero error messages or hints.
* **Real-time Web Search:** The Butler accesses live web search (DuckDuckGo free out of the box, or Tavily) when users ask for anime releases, manga chapters, game updates, patch notes, or today's news.
* **Short-Term Conversational Memory:** Maintains natural short-term context per group with automated TTL cleanup.

---

## 🏛 Architecture Overview

```text
                  Telegram Cloud
                        │
                        ▼
                ┌───────────────┐
                │  aiogram 3.x  │
                └───────┬───────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌──────────────────┐         ┌───────────────────┐
│ Translator Layer │         │  Butler AI Layer  │
├──────────────────┤         ├───────────────────┤
│ 2-Stage Detector │         │ Intent Classifier │
│ Slang/Profanity  │         │ Personality Engine│
│ LLM Engine       │         │ Real-time Web     │
│ Quality Filter   │         │ Short-Term Memory │
└────────┬─────────┘         └─────────┬─────────┘
         │                             │
         └──────────────┬──────────────┘
                        ▼
         ┌─────────────────────────────┐
         │ Database & Cache Layer      │
         │ - Async SQLAlchemy (SQLite) │
         │ - In-Memory LRU/TTL Cache   │
         └─────────────────────────────┘
```

---

## ⚙️ Telegram Bot Configuration (BotFather)

> [!IMPORTANT]
> **Telegram Group Privacy Mode:**
> By default, Telegram prevents bots from seeing group messages unless someone tags them.
> To allow the bot to automatically detect and translate foreign messages from group members:
> 1. Open Telegram and message [@BotFather](https://t.me/BotFather).
> 2. Send `/setprivacy`.
> 3. Select your bot.
> 4. Choose **`Disable`**.
> Alternatively, grant the bot **Admin** status in your group.

---

## 🛠 Linux VPS Deployment Guide

### Option 1: Docker Compose (Recommended)

1. **Clone the repository to your VPS:**
   ```bash
   git clone <your-repo-url> /opt/telegram-butler
   cd /opt/telegram-butler
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Fill in:
   - `TELEGRAM_BOT_TOKEN`
   - `OWNER_IDS` (your Telegram user ID)
   - `GEMINI_API_KEY`

3. **Start the bot:**
   ```bash
   docker compose up -d --build
   ```

4. **Monitor live logs:**
   ```bash
   docker compose logs -f bot
   ```

---

### Option 2: Systemd Service (Direct Python Run)

1. **Install system dependencies:**
   ```bash
   sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
   ```

2. **Create virtual environment:**
   ```bash
   cd /opt/telegram-butler
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure systemd:**
   Create `/etc/systemd/system/telegram-butler.service`:
   ```ini
   [Unit]
   Description=Telegram Multilingual Translator and Butler AI
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/telegram-butler
   ExecStart=/opt/telegram-butler/venv/bin/python -m bot.main
   Restart=always
   RestartSec=5
   EnvironmentFile=/opt/telegram-butler/.env

   [Install]
   WantedBy=multi-user.target
   ```

4. **Enable and start service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-butler
   sudo systemctl start telegram-butler
   sudo journalctl -u telegram-butler -f
   ```

---

## ☁️ Deploy on Render (1-Click or Manual)

### Deploy as a Web Service on Render:
1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service**.
2. Connect repository: `https://github.com/dexmrfool/EzicYeagerbot.git`.
3. Configure the service settings:
   - **Environment:** `Python` (or `Docker`)
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python -m bot.main`
   - **Plan:** Free
   - **Health Check Path:** `/health`
4. Add the following **Environment Variables** in Render:
   - `TELEGRAM_BOT_TOKEN`: `8834177471:AAH_RfDnZ_XV15qO05ZVBcM6HXZuBzikGGE`
   - `GEMINI_API_KEY`: *(Your Google Gemini API Key)*
   - `OWNER_IDS`: `5429173364`
   - `OWNER_USERNAMES`: `Merlin_hermis`
   - `DEFAULT_TARGET_LANGUAGE`: `en`
   - `DEFAULT_TRANSLATION_MODEL`: `gemini-3.6-flash`
   - `TRANSLATION_PROVIDER`: `gemini`
   - `DATABASE_URL`: `sqlite+aiosqlite:///data/bot.db`
5. Click **Deploy Web Service**!

> [!TIP]
> The bot includes an integrated HTTP health check server running on `$PORT` that responds `200 OK` to Render's `/health` checks. To keep the free instance running 24/7 without idle spin-down, you can add your Render service URL (e.g., `https://ezicyeagerbot.onrender.com/health`) to a free uptime monitor such as [UptimeRobot](https://uptimerobot.com) or [cron-job.org](https://cron-job.org) pinging every 10 minutes.

---

## 🔒 Owner Commands Summary

| Command | Visibility | Permission | Action |
| :--- | :--- | :--- | :--- |
| `/enable` | Completely Hidden | `OWNER_IDS` only | Silently activates Butler AI in the group. |
| `/disable` | Completely Hidden | `OWNER_IDS` only | Silently deactivates Butler AI. Translation remains active. |

---

## 🧪 Testing & Verification

Run the test suite locally:
```bash
python -m unittest discover tests
```
