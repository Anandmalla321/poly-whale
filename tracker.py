import requests
import json
import time
import os
from datetime import datetime

# ============================================================
#  POLYMARKET WHALE TRACKER
#  Monitors wallet trades and sends Telegram alerts instantly
# ============================================================

# ── CONFIG ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "YOUR_CHAT_ID_HERE")

WHALE_WALLETS = [
    os.environ.get("WHALE_1", "WALLET_ADDRESS_1"),
    os.environ.get("WHALE_2", "WALLET_ADDRESS_2"),
]

WHALE_NAMES = {
    WHALE_WALLETS[0]: "🐋 Whale #1",
    WHALE_WALLETS[1]: "🐋 Whale #2",
}

CHECK_INTERVAL = 30  # seconds between checks
# ────────────────────────────────────────────────────────────

seen_trades = set()  # tracks already-notified trades

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print(f"[Telegram Error] {r.text}")
    except Exception as e:
        print(f"[Telegram Exception] {e}")

def get_wallet_trades(wallet: str):
    """Fetch recent trades for a wallet from Polymarket API"""
    try:
        url = f"https://data-api.polymarket.com/activity?user={wallet.lower()}&limit=20"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception as e:
        print(f"[Fetch Error] {wallet[:10]}... → {e}")
        return []

def get_market_info(condition_id: str):
    """Get market question from condition ID"""
    try:
        url = f"https://clob.polymarket.com/markets/{condition_id}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("question", "Unknown Market")
        return "Unknown Market"
    except:
        return "Unknown Market"

def format_alert(wallet: str, trade: dict) -> str:
    """Format a clean Telegram alert message"""
    name       = WHALE_NAMES.get(wallet, f"🐋 Whale {wallet[:6]}...")
    short_addr = f"{wallet[:6]}...{wallet[-4:]}"

    # Extract trade details
    side       = trade.get("side", "UNKNOWN").upper()
    size       = float(trade.get("size", 0))
    price      = float(trade.get("price", 0))
    outcome    = trade.get("outcome", "")
    title      = trade.get("title", trade.get("market", ""))
    timestamp  = trade.get("timestamp", "")
    trade_type = trade.get("type", "trade")

    # Calculate USD value
    usd_value  = size * price if price > 0 else size

    # Direction emoji
    if side == "BUY":
        direction = "🟢 BUY"
    elif side == "SELL":
        direction = "🔴 SELL"
    else:
        direction = f"⚪ {side}"

    # Format time
    try:
        if timestamp:
            dt = datetime.fromtimestamp(int(timestamp))
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except:
        time_str = str(timestamp)

    # Outcome label
    outcome_display = f"<b>{outcome}</b>" if outcome else "N/A"

    # Size formatting
    if usd_value >= 1000:
        size_display = f"${usd_value:,.0f} USDC"
    else:
        size_display = f"${usd_value:.2f} USDC"

    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{name} TRADE ALERT\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👛 <code>{short_addr}</code>\n"
        f"📊 {direction}\n"
        f"🎯 Outcome: {outcome_display}\n"
        f"💰 Size: <b>{size_display}</b>\n"
        f"📈 Price: {price:.3f} ({price*100:.1f}%)\n"
        f"❓ Market:\n<i>{title}</i>\n"
        f"⏰ Time: {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Copy this trade NOW on Polymarket</b>"
    )
    return msg

def check_wallet(wallet: str):
    """Check a wallet for new trades and send alerts"""
    trades = get_wallet_trades(wallet)
    new_alerts = 0

    for trade in trades:
        # Build a unique ID for this trade
        trade_id = (
            trade.get("id") or
            trade.get("transactionHash") or
            f"{wallet}-{trade.get('timestamp','')}-{trade.get('size','')}-{trade.get('outcome','')}"
        )

        if trade_id in seen_trades:
            continue  # already notified

        seen_trades.add(trade_id)

        # Skip very small trades (dust)
        size  = float(trade.get("size", 0))
        price = float(trade.get("price", 0))
        usd   = size * price if price > 0 else size
        if usd < 10:
            continue

        msg = format_alert(wallet, trade)
        send_telegram(msg)
        new_alerts += 1
        print(f"[ALERT SENT] {wallet[:10]}... | ${usd:.0f} | {trade.get('outcome','?')}")
        time.sleep(0.5)  # avoid Telegram rate limit

    return new_alerts

def startup_message():
    wallets_display = "\n".join([
        f"  • {WHALE_NAMES.get(w, '🐋')} <code>{w[:6]}...{w[-4:]}</code>"
        for w in WHALE_WALLETS
    ])
    msg = (
        f"🚀 <b>Polymarket Whale Tracker STARTED</b>\n\n"
        f"👀 Watching wallets:\n{wallets_display}\n\n"
        f"⏱ Check interval: every {CHECK_INTERVAL} seconds\n"
        f"✅ You will be notified instantly on every trade!\n\n"
        f"<i>Powered by FX Oracle Whale Tracker</i>"
    )
    send_telegram(msg)

def main():
    print("=" * 50)
    print("  POLYMARKET WHALE TRACKER")
    print("=" * 50)
    print(f"  Watching {len(WHALE_WALLETS)} wallets")
    print(f"  Check interval: {CHECK_INTERVAL}s")
    print(f"  Telegram: configured")
    print("=" * 50)

    startup_message()

    # Pre-load existing trades so we don't alert on old ones
    print("\n[Init] Loading existing trades (no alerts for old ones)...")
    for wallet in WHALE_WALLETS:
        trades = get_wallet_trades(wallet)
        for trade in trades:
            trade_id = (
                trade.get("id") or
                trade.get("transactionHash") or
                f"{wallet}-{trade.get('timestamp','')}-{trade.get('size','')}-{trade.get('outcome','')}"
            )
            seen_trades.add(trade_id)
        print(f"  ✓ {WHALE_NAMES.get(wallet, wallet[:10]+'...')} — {len(trades)} existing trades cached")

    print(f"\n[Live] Now watching for NEW trades...\n")

    # Main loop
    while True:
        try:
            for wallet in WHALE_WALLETS:
                alerts = check_wallet(wallet)
                if alerts == 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No new trades — {WHALE_NAMES.get(wallet, wallet[:10]+'...')}")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n[Stopped] Tracker shut down.")
            send_telegram("⛔ Whale Tracker has been stopped.")
            break
        except Exception as e:
            print(f"[Error] {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
