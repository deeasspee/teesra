# market_data.py
# Teesra — Fetches Sensex and Nifty data from Yahoo Finance
# Free, no API key needed

import json
import urllib.request
from datetime import datetime, date
import time


def fetch_index(symbol: str, name: str) -> dict:
    """Fetch a single market index from Yahoo Finance"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        result = data["chart"]["result"][0]
        meta = result["meta"]

        current = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("chartPreviousClose", 0)

        if prev_close and prev_close > 0:
            change = current - prev_close
            change_pct = (change / prev_close) * 100
        else:
            change = 0
            change_pct = 0

        return {
            "name": name,
            "symbol": symbol,
            "current": round(current, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 2),
            "direction": "up" if change >= 0 else "down",
            "fetched_at": str(datetime.now())
        }

    except Exception as e:
        print(f"  ⚠️ Could not fetch {name}: {e}")
        return {
            "name": name,
            "symbol": symbol,
            "current": 0,
            "change": 0,
            "change_pct": 0,
            "prev_close": 0,
            "direction": "flat",
            "fetched_at": str(datetime.now())
        }


def fetch_market_data() -> dict:
    """Fetch all market indices"""
    print("  📈 Fetching market data...")

    indices = {
        "sensex": fetch_index("^BSESN", "Sensex"),
        "nifty": fetch_index("^NSEI", "Nifty 50"),
        "bank_nifty": fetch_index("^NSEBANK", "Bank Nifty"),
    }

    # Add market summary
    sensex = indices["sensex"]
    nifty = indices["nifty"]

    if sensex["current"] > 0 and nifty["current"] > 0:
        if sensex["direction"] == "up" and nifty["direction"] == "up":
            mood = "📈 Markets closed in the green"
        elif sensex["direction"] == "down" and nifty["direction"] == "down":
            mood = "📉 Markets closed in the red"
        else:
            mood = "↔️ Markets closed mixed"
    else:
        mood = "Markets data unavailable"

    indices["mood"] = mood
    indices["date"] = str(date.today())
    indices["as_of"] = datetime.now().strftime("%d %b %Y, %I:%M %p IST")

    print(f"  ✅ {mood}")
    print(f"     Sensex: {sensex['current']:,.2f} ({'+' if sensex['change'] >= 0 else ''}{sensex['change_pct']:.2f}%)")
    print(f"     Nifty:  {nifty['current']:,.2f} ({'+' if nifty['change'] >= 0 else ''}{nifty['change_pct']:.2f}%)")

    return indices


def fetch_commodity_data() -> dict:
    """Fetch gold/silver/USD-INR from Yahoo Finance via yfinance"""
    try:
        import yfinance as yf

        gold_info   = yf.Ticker("GC=F").fast_info
        silver_info = yf.Ticker("SI=F").fast_info
        fx_info     = yf.Ticker("INR=X").fast_info

        gold_usd        = gold_info.last_price or 0
        gold_usd_prev   = gold_info.previous_close or gold_usd
        silver_usd      = silver_info.last_price or 0
        silver_usd_prev = silver_info.previous_close or silver_usd
        usd_inr         = fx_info.last_price or 84.0

        gpg      = (gold_usd      / 31.1035) * usd_inr
        gpg_prev = (gold_usd_prev / 31.1035) * usd_inr

        gold_24k      = round(gpg * 10)
        gold_24k_prev = round(gpg_prev * 10)
        gold_22k      = round(gpg * 10 * 22 / 24)

        silver_kg      = round((silver_usd      / 31.1035) * usd_inr * 1000)
        silver_kg_prev = round((silver_usd_prev / 31.1035) * usd_inr * 1000)

        def pct(curr, prev):
            if not prev: return 0.0
            return round((curr - prev) / prev * 100, 2)

        gold_chg_pct   = pct(gold_24k,  gold_24k_prev)
        silver_chg_pct = pct(silver_kg, silver_kg_prev)

        return {
            "gold_24k":        gold_24k,
            "gold_24k_pct":    gold_chg_pct,
            "gold_24k_dir":    "up" if gold_chg_pct >= 0 else "down",
            "gold_22k":        gold_22k,
            "silver_kg":       silver_kg,
            "silver_kg_pct":   silver_chg_pct,
            "silver_kg_dir":   "up" if silver_chg_pct >= 0 else "down",
            "usd_inr":         round(usd_inr, 2),
        }
    except Exception as e:
        print(f"  Warning: Commodity data failed: {e}")
        return None


def format_market_for_email(market):
    """Returns HTML snippet for newsletter (Sensex, Nifty, Bank Nifty)."""
    if not market:
        return ""

    sensex     = market.get("sensex", {})
    nifty      = market.get("nifty", {})
    bank_nifty = market.get("bank_nifty", {})

    def arrow(d):
        return "&#9650;" if d == "up" else "&#9660;"

    def clr(d):
        return "#7bc67e" if d == "up" else "#d45b5b"

    def fmt(v):
        try:
            return "{:,.2f}".format(v) if v else "-"
        except Exception:
            return "-"

    def cell(label, idx_dict):
        d   = idx_dict.get("direction", "flat")
        pct = abs(idx_dict.get("change_pct", 0))
        return (
            '<td style="padding:4px 16px;border-left:1px solid #2a2a1f;white-space:nowrap;">'
            '<p style="margin:0 0 2px 0;font-family:monospace;font-size:9px;color:#7a7660;">' + label + '</p>'
            '<p style="margin:0;font-size:15px;font-weight:700;color:#e8e4d4;font-family:Georgia,serif;">' + fmt(idx_dict.get("current", 0)) + '</p>'
            '<p style="margin:0;font-size:11px;color:' + clr(d) + ';">' + arrow(d) + ' ' + "{:.2f}".format(pct) + '%</p>'
            '</td>'
        )

    sensex_cell     = cell("SENSEX",     sensex)
    nifty_cell      = cell("NIFTY 50",   nifty)
    bank_nifty_cell = cell("BANK NIFTY", bank_nifty)

    return (
        '<table width="100%" cellpadding="0" cellspacing="0"'
        ' style="background:#0f0f0a;border:1px solid #2a2a1f;margin-bottom:20px;">'
        '<tr><td style="padding:10px 20px;border-bottom:1px solid #2a2a1f;">'
        '<p style="margin:0;font-family:monospace;font-size:9px;color:#e8c84a;'
        'letter-spacing:2px;text-transform:uppercase;">Markets - Last Close</p>'
        '</td></tr>'
        '<tr><td style="padding:10px 20px;">'
        '<table cellpadding="0" cellspacing="0"><tr>'
        + sensex_cell + nifty_cell + bank_nifty_cell +
        '</tr></table>'
        '</td></tr>'
        '</table>'
    )


def format_market_for_feed(market: dict) -> dict:
    """Returns clean dict for feed UI"""
    return {
        "sensex": market.get("sensex", {}),
        "nifty": market.get("nifty", {}),
        "bank_nifty": market.get("bank_nifty", {}),
        "mood": market.get("mood", ""),
        "date": market.get("date", "")
    }


if __name__ == "__main__":
    print("\n📊 Testing market data fetch...\n")
    data = fetch_market_data()
    print("\nRaw data:")
    print(json.dumps(data, indent=2))