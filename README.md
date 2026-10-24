# BOS Telegram bot

Sends an alert (Telegram, and optionally email and WhatsApp) when a candle **closes** beyond the current BOS level on
**XAUUSD** and **GBPUSD**, on **15m, 1H and 4H**. It uses the same rules as the BOS Scanner
TradingView script ("Gap" mode, at least 2 candles after a high/low).

It runs on GitHub Actions every 15 minutes (2 minutes after each 15m candle closes), Sunday to Friday.
GitHub's scheduler can run a few minutes late.

Example message:

```
XAUUSD
1H bearish BOS
22 Oct 2026, 5:30 PM IST
```
The time is when the breaking candle closed.

## One-time setup

### 1. Telegram bot
1. In Telegram, open **@BotFather** → send `/newbot` → pick a name and a username ending in `bot`.
2. BotFather replies with a **token** (looks like `123456789:AA...`). Keep it private.
3. Open your new bot in Telegram and press **Start** (or send it any message).
4. In a browser, open `https://api.telegram.org/bot<TOKEN>/getUpdates` (put your token in place of `<TOKEN>`).
   Find `"chat":{"id":` — that number is your **chat ID**.

### 2. Twelve Data (price data, free)
Sign up at twelvedata.com (free Basic plan) and copy your **API key** from the dashboard.
The bot uses about 200 of the 800 free requests per day.

### 3. GitHub secrets
In the GitHub repository: **Settings → Secrets and variables → Actions → New repository secret**, add:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather |
| `TELEGRAM_CHAT_ID` | your chat ID |
| `TWELVEDATA_API_KEY` | your Twelve Data API key |

### 4. Email alerts (optional)
Uses Gmail by default. Gmail needs an **app password** (your normal password won't work):
1. Turn on 2-Step Verification for your Google account.
2. Open **myaccount.google.com/apppasswords**, create one (name it e.g. "BOS bot") and copy the 16-letter password.
3. Add these GitHub secrets:

| Name | Value |
|---|---|
| `SMTP_USER` | your Gmail address (the alert is sent from it) |
| `SMTP_PASSWORD` | the app password |
| `EMAIL_TO` | where to send alerts (can be the same address; separate several with commas) |

Other providers: also add `SMTP_HOST` (e.g. `smtp.office365.com`) and `SMTP_PORT` (`465`, or `587`).
The email subject is the alert itself, e.g. "XAUUSD 1H bearish BOS".

### 5. WhatsApp alerts (optional)
Uses **CallMeBot**, a free service that sends WhatsApp messages to your own number.
1. Follow the steps on **callmebot.com → WhatsApp API**: save their number in your contacts and send it
   the activation message they show. It replies with your **API key** (this can take a few minutes).
2. Add these GitHub secrets:

| Name | Value |
|---|---|
| `WHATSAPP_PHONE` | your number with country code, e.g. `+919876543210` |
| `CALLMEBOT_API_KEY` | the API key CallMeBot sent you |

CallMeBot is free for personal use, but it's a small free service: it can be slow at times. Keep
Telegram or email on as well.

Each channel turns on when all of its secrets are set. Telegram is optional too, but at least one channel
must be set up. If one channel fails, the others still get the alert, and that run shows as failed in
the Actions tab.

### 6. Test
**Actions → BOS alerts → Run workflow**, tick **"Only send a test message"** → Run.
You should get a "BOS bot is connected" message on every channel you set up.

Then run it once more **without** the tick. The first normal run only records the latest BOS
(so you don't get a flood of old ones); alerts start from the next new BOS.

## Notes
- **Prices** come from Twelve Data, not FOREX.com, so a level can differ by a few pips/cents from your chart.
  On a very close break, one may show a BOS and the other not.
- **Starting levels** come from the last ~52 days of 15m data. On 4H that's about 300 candles, so very old
  structure can differ slightly from TradingView, which loads more history. Recent BOS levels match once
  a couple of BOS have happened.
- `state.json` remembers which BOS were already sent. The bot commits it after each run that sends something.
- GitHub pauses scheduled workflows in repositories with no commits for 60 days. The state commits normally
  keep it active; if it ever pauses, re-enable it in the Actions tab.

## Run it on your Mac (optional)
```
TWELVEDATA_API_KEY=... python3 bos_bot.py --levels
```
`--levels` prints the current BOS levels and the last BOS for each pair/timeframe.
`--source yahoo` uses Yahoo Finance data instead (no key needed; gold there is futures, a few dollars off spot).
