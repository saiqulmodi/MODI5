"""
MODI5: read-only Angel One portfolio monitor. NEVER places any order --
every signal here is purely informational, for you to act on manually in
the Angel app. Two independent things are checked each run:

  1. NEW BUY opportunities from watchlist.json (built by stock_check.py,
     same score+ML+intraday-confirmation+3-day-HH/HL-swing-structure gate
     as MODI1's buy_sell_alert.py) -- informational only, nothing here is
     bought automatically.
  2. Every stock actually held in the real Angel demat (fetched live via
     MODI4's angel_holdings.get_angel_holdings()) is checked for the
     mirror 3-day Lower-Low+Lower-High swing-structure breakdown -- if
     found, alerts "consider selling manually", independent of anything
     else (score, ML, whether it's also in the watchlist).

Only runs during market hours. Tracks state per symbol so it only alerts
on a change (watchlist side) or once per day (protective-exit side).
"""

from datetime import datetime as _dt

_now = _dt.now()
_market_start = _now.replace(hour=9, minute=15, second=0, microsecond=0)
_market_end = _now.replace(hour=15, minute=30, second=0, microsecond=0)
if _now < _market_start or _now > _market_end:
    print(f"Outside market hours ({_now.strftime('%H:%M:%S')}), skipping run.")
    exit()

import json
import os
import sys
import yfinance as yf
from send_telegram import send_telegram_message
from ml_predict import get_ml_probability
from angel_data import find_symbol_token
from intraday_confirm import get_intraday_confirmation

# Angel holdings lookup only -- MODI4 is never asked to place an order
# from this project.
sys.path.insert(0, r"C:\Users\saiqu\Projects\MODI4")
from angel_holdings import get_angel_holdings

WATCHLIST_FILE = "watchlist.json"
ALERT_STATE_FILE = "watchlist_alerted_state.json"
PROTECTIVE_STATE_FILE = "protective_exit_state.json"


def get_score_verdict(score):
    if score >= 4:
        return "BUY"
    elif score <= 1:
        return "SELL/AVOID"
    else:
        return "HOLD"


def get_combined_signal(score, ml_prob):
    if ml_prob is None:
        return "HOLD"
    verdict = get_score_verdict(score)
    if verdict == "BUY" and ml_prob >= 0.5:
        return "BUY"
    elif verdict == "SELL/AVOID" and ml_prob < 0.5:
        return "SELL/AVOID"
    else:
        return "HOLD"


# ---- Part 1: new-opportunity watchlist, same gating as MODI1, alert-only ----
alert_state = {}
if os.path.exists(ALERT_STATE_FILE):
    with open(ALERT_STATE_FILE, "r") as f:
        alert_state = json.load(f)

new_alerts = []
if os.path.exists(WATCHLIST_FILE):
    with open(WATCHLIST_FILE, "r") as f:
        watchlist = json.load(f)

    for entry in watchlist:
        symbol = entry["symbol"]
        ml_prob = get_ml_probability(symbol + ".NS")
        signal = get_combined_signal(entry["score"], ml_prob)

        intraday = None
        if signal in ("BUY", "SELL/AVOID"):
            token = find_symbol_token(symbol)
            if token:
                hist = yf.Ticker(symbol + ".NS").history(period="30d")
                intraday = get_intraday_confirmation(token, symbol, hist)

            if intraday is None:
                print(f"{symbol}: {signal} signal held back, no intraday confirmation data available")
                signal = "HOLD"
            elif signal == "BUY" and not intraday["confirms_bullish"]:
                signal = "HOLD"
            elif signal == "SELL/AVOID" and not intraday["confirms_bearish"]:
                signal = "HOLD"

        prev = alert_state.get(symbol)
        if signal != prev:
            alert_state[symbol] = signal
            if signal in ("BUY", "SELL/AVOID"):
                emoji = "🟢" if signal == "BUY" else "🔴"
                prob_str = f"{ml_prob:.0%}" if ml_prob is not None else "N/A"
                new_alerts.append(
                    f"{emoji} {symbol} ({entry['name']}): {signal} "
                    f"(score {entry['score']}, ml_prob {prob_str}) -- new opportunity, place manually if you want it"
                )
else:
    print("No watchlist.json found -- run stock_check.py first.")

# ---- Part 2: protective exit for real Angel holdings ----
protective_state = {}
if os.path.exists(PROTECTIVE_STATE_FILE):
    with open(PROTECTIVE_STATE_FILE, "r") as f:
        protective_state = json.load(f)

today_str = _now.strftime("%Y-%m-%d")
protective_alerts = []

angel_data = get_angel_holdings()
if angel_data is None:
    print("Couldn't fetch Angel holdings this run -- skipping protective-exit check.")
else:
    for h in angel_data["holdings"]:
        raw_symbol = h.get("symbol") or ""
        base_symbol = raw_symbol.split("-")[0]
        token = h.get("symboltoken")
        if not token or not base_symbol:
            continue

        try:
            hist = yf.Ticker(base_symbol + ".NS").history(period="30d")
        except Exception as e:
            print(f"{base_symbol}: history fetch error: {e}")
            continue

        intraday = get_intraday_confirmation(token, base_symbol, hist)
        if intraday is None:
            continue

        if intraday.get("swing_structure_bearish") and protective_state.get(base_symbol) != today_str:
            protective_alerts.append(
                f"🔻 {base_symbol}: 3-day Lower-Low+Lower-High breakdown -- "
                f"held qty {h['quantity']}, LTP {intraday['current_price']}, "
                f"P&L so far Rs.{h['pnl']} ({h['pnl_pct']}%). Consider selling manually."
            )
            protective_state[base_symbol] = today_str

# ---- Send alerts ----
all_alerts = new_alerts + protective_alerts
if all_alerts:
    CHUNK_SIZE = 40
    total_sent_ok = True
    for i in range(0, len(all_alerts), CHUNK_SIZE):
        chunk = all_alerts[i:i + CHUNK_SIZE]
        part_num = (i // CHUNK_SIZE) + 1
        total_parts = (len(all_alerts) + CHUNK_SIZE - 1) // CHUNK_SIZE
        header = f"*MODI5 Angel Alert* (part {part_num}/{total_parts})" if total_parts > 1 else "*MODI5 Angel Alert*"
        message = header + "\n" + "\n".join(chunk)
        sent = send_telegram_message(message)
        if not sent:
            total_sent_ok = False
    print(f"Sent {len(all_alerts)} alert(s). Telegram sent: {total_sent_ok}")
else:
    print("No alerts this run.")

with open(ALERT_STATE_FILE, "w") as f:
    json.dump(alert_state, f, indent=2)

protective_state = {k: v for k, v in protective_state.items() if v == today_str}
with open(PROTECTIVE_STATE_FILE, "w") as f:
    json.dump(protective_state, f, indent=2)
