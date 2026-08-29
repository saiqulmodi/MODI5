# MODI5 — Read-Only Angel One Portfolio Monitor

**Never places any order** — every signal is informational only, for you to
act on manually in the Angel app. `watchlist_alert.py` checks two things
each run: (1) new BUY opportunities from `watchlist.json` (built by
`stock_check.py`, same scoring gate as MODI1), and (2) every stock actually
held in your real Angel demat (fetched live via MODI4's holdings approach)
for a 3-day Lower-Low/Lower-High swing-structure breakdown.

## Setup

None of the credential files below are committed — each is gitignored
because it holds live broker secrets. Recreate them locally with your own
values before running anything.

### `angel_login.py`

Same template as MODI1's README — see
[MODI1/README.md](https://github.com/saiqulmodi/modi1#setup) for the full
file content.

### `send_telegram.py`

```python
import requests

BOT_TOKEN = "your-bot-token-here"
CHAT_ID = "your-chat-id-here"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        print(f"Telegram send failed: {response.text}")
    return response.status_code == 200
```

## Running

- `run_stock_check.bat` — runs `stock_check.py` (scores the watchlist, writes `watchlist.json`)
- `run_watchlist_alert.bat` — runs `watchlist_alert.py` (the informational monitor)

`price_model.pkl` is gitignored — MODI5 reuses the same trained model as
MODI1 (retrain there if it ever needs updating, then copy across).
`watchlist.json` is intentionally tracked, not ignored — see MODI1's README
for why. `watchlist_alerted_state.json` and `protective_exit_state.json` are
gitignored generated state.
