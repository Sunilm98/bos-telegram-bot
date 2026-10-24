# BOS Telegram bot

Sends a Telegram message when a candle **closes** beyond the current BOS level on
**XAUUSD** and **GBPUSD**, on **15m, 1H and 4H**. It uses the same rules as the BOS Scanner
TradingView script ("Gap" mode, at least 2 candles after a high/low).

It runs on GitHub Actions every 15 minutes (2 minutes after each 15m candle closes), Sunday to Friday.
GitHub's scheduler can run a few minutes late.

Example message:

```
XAUUSD
1H bearish BOS
22 Oct 2026, 17:30 IST
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

### 4. Test
**Actions → BOS alerts → Run workflow**, tick **"Only send a test message"** → Run.
You should get a "BOS bot is connected" message in Telegram.

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
