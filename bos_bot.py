"""BOS alert bot.

Checks each pair on 15m, 1H and 4H after candles close and sends a Telegram message
when a candle closes beyond the current BOS level. Same rules as bos_scanner.pine
("Gap" mode, at least 2 candles after a high/low).

Usage:
  python bos_bot.py              check for new BOS and send Telegram alerts
  python bos_bot.py --levels     print the current BOS levels and last BOS for each pair/timeframe
  python bos_bot.py --test       send a test message to Telegram
  python bos_bot.py --dry-run    check, but print alerts instead of sending them
  add --source yahoo to use Yahoo Finance data instead of Twelve Data (for local testing; gold is futures there)

Settings come from environment variables: TWELVEDATA_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ── Settings ──────────────────────────────────────────────────────────────
# pair name → (Twelve Data symbol, Yahoo symbol, decimals shown)
PAIRS = {
    "XAUUSD": ("XAU/USD", "GC=F", 2),
    "GBPUSD": ("GBP/USD", "GBPUSD=X", 5),
}
TIMEFRAMES = {"15m": 15, "1H": 60, "4H": 240}
MIN_AFTER = 2        # candles that must close after a high/low before it counts (with the gap)
SEED_LEN = 5         # swing length for the starting levels, before the first BOS
MAX_ALERT_AGE = timedelta(hours=12)   # never alert on a BOS older than this (e.g. after a long outage)

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
NY = ZoneInfo("America/New_York")     # FX sessions (and TradingView's 4H candles) start at 17:00 New York
IST = ZoneInfo("Asia/Kolkata")         # time shown in messages


# ── Price data ────────────────────────────────────────────────────────────
# A candle is (start_utc, open, high, low, close)

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_twelvedata(symbol):
    key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    if not key:
        sys.exit("TWELVEDATA_API_KEY is not set")
    q = urllib.parse.urlencode({"symbol": symbol, "interval": "15min", "outputsize": 5000,
                                "timezone": "UTC", "order": "asc", "apikey": key})
    data = get_json(f"https://api.twelvedata.com/time_series?{q}")
    if data.get("status") != "ok":
        raise RuntimeError(f"Twelve Data error for {symbol}: {data.get('message', data)}")
    return [(datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
             float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"]))
            for v in data["values"]]


def fetch_yahoo(symbol):
    q = urllib.parse.urlencode({"interval": "15m", "range": "60d"})
    r = get_json(f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{q}")["chart"]["result"][0]
    q15 = r["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(r["timestamp"]):
        o, h, l, c = q15["open"][i], q15["high"][i], q15["low"][i], q15["close"][i]
        start = datetime.fromtimestamp(t, timezone.utc)
        if None not in (o, h, l, c) and start.minute % 15 == 0 and start.second == 0:
            out.append((start, o, h, l, c))
    return out


def closed_candles(c15, minutes, now):
    """Build candles of `minutes` from 15m candles, aligned like TradingView FX charts. Only fully closed candles."""
    c15 = sorted(c for c in c15 if c[0] + timedelta(minutes=15) <= now)
    if minutes == 15:
        return c15
    out = []
    for start, o, h, l, c in c15:
        local = start.astimezone(NY)
        since_open = (local.hour * 60 + local.minute - 17 * 60) % 1440
        bucket = start - timedelta(minutes=since_open % minutes)
        if out and out[-1][0] == bucket:
            b = out[-1]
            out[-1] = (bucket, b[1], max(b[2], h), min(b[3], l), c)
        else:
            out.append((bucket, o, h, l, c))
    return [b for b in out if b[0] + timedelta(minutes=minutes) <= now]


# ── BOS logic (port of bos_scanner.pine, Gap mode) ────────────────────────
def find_bos(candles, minutes):
    H = [c[2] for c in candles]
    L = [c[3] for c in candles]
    C = [c[4] for c in candles]
    n = len(candles)
    close_time = lambda i: candles[i][0] + timedelta(minutes=minutes)

    s_high = s_high_bar = s_low = s_low_bar = None
    hi_pending = lo_pending = False
    p_high = p_high_bar = p_low = p_low_bar = None
    hi_gap = lo_gap = False
    started = False
    events = []

    def pivot(i, is_high):
        p = i - SEED_LEN
        if p - SEED_LEN < 0:
            return None
        v = H[p] if is_high else L[p]
        for j in range(p - SEED_LEN, i + 1):
            if j != p and ((is_high and H[j] >= v) or (not is_high and L[j] <= v)):
                return None
        return v

    for i in range(n):
        if not started:
            ph, pl = pivot(i, True), pivot(i, False)
            if ph is not None:
                s_high, s_high_bar = ph, i - SEED_LEN
            if pl is not None:
                s_low, s_low_bar = pl, i - SEED_LEN

        # Confirm the pending high/low: a gap (wick poking past the previous candle) and at least MIN_AFTER candles
        if hi_pending:
            if H[i] > p_high:
                p_high, p_high_bar, hi_gap = H[i], i, False
            else:
                if L[i] < L[i - 1] and i - 1 >= p_high_bar:
                    hi_gap = True
                if hi_gap and i - p_high_bar >= MIN_AFTER:
                    hi_pending, s_high, s_high_bar = False, p_high, p_high_bar
        if lo_pending:
            if L[i] < p_low:
                p_low, p_low_bar, lo_gap = L[i], i, False
            else:
                if H[i] > H[i - 1] and i - 1 >= p_low_bar:
                    lo_gap = True
                if lo_gap and i - p_low_bar >= MIN_AFTER:
                    lo_pending, s_low, s_low_bar = False, p_low, p_low_bar

        # Bullish BOS: candle closes above the structure high
        if s_high is not None and C[i] > s_high:
            lo, lo_bar = L[i], i
            for j in range(i - 1, s_high_bar, -1):   # the high candle itself is skipped
                if L[j] < lo:
                    lo, lo_bar = L[j], j
            events.append({"dir": 1, "level": s_high, "close": C[i], "swing": lo, "time": close_time(i)})
            s_low, s_low_bar, lo_pending, s_high = lo, lo_bar, False, None
            pk = i
            for j in range(i - 1, lo_bar - 1, -1):
                if H[j] > H[pk]:
                    pk = j
            p_high, p_high_bar, hi_pending, started = H[pk], pk, True, True
            hi_gap = any(L[k] < L[k - 1] for k in range(pk + 1, i + 1))

        # Bearish BOS: candle closes below the structure low
        if s_low is not None and C[i] < s_low:
            hi, hi_bar = H[i], i
            for j in range(i - 1, s_low_bar, -1):    # the low candle itself is skipped
                if H[j] > hi:
                    hi, hi_bar = H[j], j
            events.append({"dir": -1, "level": s_low, "close": C[i], "swing": hi, "time": close_time(i)})
            s_high, s_high_bar, hi_pending, s_low = hi, hi_bar, False, None
            tr = i
            for j in range(i - 1, hi_bar - 1, -1):
                if L[j] < L[tr]:
                    tr = j
            p_low, p_low_bar, lo_pending, started = L[tr], tr, True, True
            lo_gap = any(H[k] > H[k - 1] for k in range(tr + 1, i + 1))

    return events, s_high, s_low


# ── Telegram ──────────────────────────────────────────────────────────────
def send_telegram(text):
    # Strip stray spaces/line breaks that often come along when a value is copied and pasted
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        sys.exit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=30) as r:
            json.load(r)
    except urllib.error.HTTPError as e:
        # Telegram explains the problem in the response body (e.g. "chat not found"); it never contains the token
        try:
            reason = json.load(e).get("description", "")
        except Exception:
            reason = ""
        sys.exit(f"Telegram rejected the message (HTTP {e.code}): {reason}")


def message(pair, tf, ev):
    t = ev["time"].astimezone(IST)   # when the breaking candle closed
    when = f"{t:%d %b %Y}, {t.hour % 12 or 12}:{t:%M %p} IST"
    return f"{pair}\n{tf} {'bullish' if ev['dir'] == 1 else 'bearish'} BOS\n{when}"


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["twelvedata", "yahoo"], default="twelvedata")
    ap.add_argument("--dry-run", action="store_true", help="print alerts instead of sending them")
    ap.add_argument("--levels", action="store_true", help="print current BOS levels and exit")
    ap.add_argument("--test", action="store_true", help="send a test message and exit")
    args = ap.parse_args()

    if args.test:
        send_telegram("✅ BOS bot is connected. You'll get a message here when a candle closes beyond a BOS level.")
        print("Test message sent")
        return

    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)

    now = datetime.now(timezone.utc)
    failed = False
    for pair, (td_sym, yahoo_sym, dec) in PAIRS.items():
        try:
            c15 = fetch_twelvedata(td_sym) if args.source == "twelvedata" else fetch_yahoo(yahoo_sym)
        except Exception as e:
            print(f"{pair}: could not fetch prices: {e}")
            failed = True
            continue
        for tf, minutes in TIMEFRAMES.items():
            events, s_high, s_low = find_bos(closed_candles(c15, minutes, now), minutes)
            key = f"{pair}_{tf}"
            if args.levels:
                e = events[-1] if events else None
                last = (f"{'bullish' if e['dir'] == 1 else 'bearish'} BOS at {e['level']:.{dec}f}, "
                        f"candle closed {e['time'].astimezone(IST):%d %b %H:%M} IST") if e else "no BOS yet"
                fmt = lambda x: "pending" if x is None else f"{x:.{dec}f}"
                print(f"{pair} {tf}: next BOS high {fmt(s_high)}, next BOS low {fmt(s_low)}\n   last: {last}")
                continue
            if key not in state:
                # First run: remember the latest BOS without alerting on old ones
                state[key] = events[-1]["time"].isoformat() if events else now.isoformat()
                continue
            last_sent = datetime.fromisoformat(state[key])
            for ev in events:
                if ev["time"] > last_sent and now - ev["time"] <= MAX_ALERT_AGE:
                    text = message(pair, tf, ev)
                    if args.dry_run:
                        print("ALERT:\n" + text)
                    else:
                        send_telegram(text)
                    state[key] = ev["time"].isoformat()
                elif ev["time"] > last_sent:
                    state[key] = ev["time"].isoformat()

    if not args.levels and not args.dry_run:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
