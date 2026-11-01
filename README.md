# BOS Telegram bot

Sends an alert (Telegram, and optionally email and WhatsApp) when a candle **closes** beyond the current BOS level on
**XAUUSD** and **GBPUSD**, on **15m, 1H and 4H**. It uses the same rules as the BOS Scanner
TradingView script ("Gap" mode, at least 3 candles after a high/low and a pullback of at least 1 × ATR 14).

It runs on GitHub Actions every 15 minutes (2 minutes after each 15m candle closes). GitHub's own
scheduler often runs hours late or skips runs, so a free timer on cron-job.org starts it on time instead
(see "On-time runs" below). GitHub's schedule stays on as a backup.

Example message:

```
XAUUSD
1H bearish BOS
22 Oct 2026, 5:30 PM IST
```
The time is when the breaking candle closed. When several timeframes break on the same candle close, they share one message,
e.g. "15m + 1H bearish BOS".

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
Uses **Brevo** (free: 300 emails a day), which is made for automated email. Gmail often refuses
sign-ins from GitHub's servers, so it's not used by default.
1. Sign up at **brevo.com** (free plan) and confirm your email address.
2. Go to **Settings → SMTP & API → SMTP** (top-right menu → *SMTP & API*). Click **Generate a new SMTP key**,
   name it "BOS bot" and copy the key (it starts with `xsmtpsib-`). Brevo shows it only once.
3. On the same page, note the **Login** (looks like `8a1b2c001@smtp-brevo.com`).
4. Add these GitHub secrets:

| Name | Value |
|---|---|
| `SMTP_HOST` | `smtp-relay.brevo.com` |
| `SMTP_USER` | the Brevo **Login** |
| `SMTP_PASSWORD` | the Brevo **SMTP key** |
| `EMAIL_FROM` | the email you signed up to Brevo with (Brevo only sends from verified addresses) |
| `EMAIL_TO` | where to send alerts (can be the same address; separate several with commas) |

The email subject is the alert itself, e.g. "XAUUSD 1H bearish BOS". The first one may land in spam:
mark it **Not spam** so later ones arrive in your inbox.

Other providers work too: set `SMTP_HOST` and, if needed, `SMTP_PORT` (`465`, the default, or `587`).
With Gmail, leave `SMTP_HOST` unset and use an app password (myaccount.google.com/apppasswords).

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
To see what a real alert looks like, run it again with **"Only send a made-up alert"** ticked instead:
you'll get an "XAUUSD 1H bearish BOS" message (it isn't a real signal).
Tick **"Only show the current BOS levels"** to see the bot's levels for each pair and timeframe in the
run's log (open the run → *scan* → *Check for new BOS*). Nothing is sent.

Then run it once more **without** the tick. The first normal run only records the latest BOS
(so you don't get a flood of old ones); alerts start from the next new BOS.

## On-time runs (cron-job.org)
GitHub's built-in schedule is "best effort" and can be hours late. cron-job.org (free) asks GitHub to
start the bot every 15 minutes instead.

1. **GitHub token** — profile picture → **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**. Name it `bos-bot timer`, pick the longest expiration,
   **Only select repositories** → `bos-telegram-bot`, and under Repository permissions set
   **Actions: Read and write**. Copy the token (`github_pat_…`) with the copy icon.
2. **cron-job.org** — sign up → **Create cronjob**:
   - URL: `https://api.github.com/repos/Sunilm98/bos-telegram-bot/actions/workflows/bos-alerts.yml/dispatches`
   - Schedule: custom, minutes `2,17,32,47`, every hour, every day
   - Advanced tab:
     - **Requires HTTP authentication**: on. Username: your GitHub username. Password: the token.
     - Header: Key `Accept`, Value `application/vnd.github+json`
     - Request method: **POST**
     - Request body: `{"ref":"main"}`
3. **Save → Test run**: it should show **204 No Content**, and a new run appears in the Actions tab.

When the token expires (GitHub emails you first), regenerate it and paste the new one into cron-job.org.
A run that starts twice (timer and GitHub's schedule) is harmless: the bot remembers what it already sent.

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
