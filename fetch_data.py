#!/usr/bin/env python3
"""
GrainBrief Data Fetcher
=======================
Run this on your laptop to pull all market data and write data.json
which the dashboard HTML reads.

Install once:
    pip install yfinance requests

Run manually:
    python fetch_data.py

Auto-run every 10 minutes (keep terminal open):
    python fetch_data.py --loop

Or set up Task Scheduler (Windows) / cron (Mac/Linux) to run at 5:50am.
"""

import yfinance as yf
import json
import time
import argparse
import os
import sys
from datetime import datetime, date
from pathlib import Path

# ─── OUTPUT FILE ───────────────────────────────────────────────────────────────
# data.json goes in the same folder as this script (and grainbrief.html)
OUTPUT = Path(__file__).parent / "data.json"

# ─── CONTRACTS ─────────────────────────────────────────────────────────────────
CONTRACTS = [
    {"sym": "ZC=F",  "label": "CBOT Corn",        "unit": "USc/bu", "cls": "corn",  "col": "#d3c149"},
    {"sym": "ZW=F",  "label": "CBOT Wheat",        "unit": "USc/bu", "cls": "wheat", "col": "#c79f44"},
    {"sym": "ZS=F",  "label": "CBOT Soybeans",     "unit": "USc/bu", "cls": "corn",  "col": "#8ab45e"},
    {"sym": "ZM=F",  "label": "CBOT Soy Meal",     "unit": "$/ton",  "cls": "corn",  "col": "#7aaa88"},
    {"sym": "KE=F",  "label": "CBOT HRW Wheat",    "unit": "USc/bu", "cls": "wheat", "col": "#b8923a"},
    # MATIF — Euronext tickers (front month, update if expired)
    {"sym": "EBM=F", "label": "MATIF Mill. Wheat", "unit": "€/t",   "cls": "wheat", "col": "#c79f44"},
    {"sym": "ECO=F", "label": "MATIF Corn",        "unit": "€/t",   "cls": "corn",  "col": "#d3c149"},
]

# YTD chart contracts
YTD_SYMS = {"ZC=F", "ZW=F", "KE=F", "EBM=F", "ECO=F"}


def fetch_prices():
    """Fetch current quotes + YTD history for all contracts."""
    print(f"[{datetime.now():%H:%M:%S}] Fetching prices...")
    prices = {}

    for c in CONTRACTS:
        sym = c["sym"]
        try:
            tk = yf.Ticker(sym)

            # Current quote
            info = tk.fast_info
            price = info.last_price
            prev  = info.previous_close
            hi    = info.day_high
            lo    = info.day_low

            # YTD history
            ytd_closes = []
            ytd_dates  = []
            if sym in YTD_SYMS:
                hist = tk.history(start=f"{date.today().year}-01-01", interval="1d", auto_adjust=True)
                if not hist.empty:
                    ytd_closes = [round(float(v), 4) for v in hist["Close"].dropna()]
                    ytd_dates  = [str(d.date()) for d in hist.index]

            prices[sym] = {
                "price":      round(float(price), 4)  if price  else None,
                "prev":       round(float(prev), 4)   if prev   else None,
                "hi":         round(float(hi), 4)     if hi     else None,
                "lo":         round(float(lo), 4)     if lo     else None,
                "change":     round(float(price - prev), 4) if price and prev else None,
                "pct":        round(((price - prev) / prev) * 100, 4) if price and prev else None,
                "ytd_closes": ytd_closes,
                "ytd_dates":  ytd_dates,
            }
            print(f"  ✓ {sym:<10} {price:.2f}  ({'+' if price-prev>=0 else ''}{price-prev:.2f})")

        except Exception as e:
            print(f"  ✗ {sym:<10} ERROR: {e}")
            prices[sym] = None

    return prices


def fetch_weather():
    """Fetch 14-day forecast from Open-Meteo (no API key needed)."""
    import urllib.request

    LOCATIONS = [
        {"name": "Iowa · Corn Belt",    "lat": 42.0, "lon": -93.6, "key": "iowa"},
        {"name": "Kansas · Wheat Belt", "lat": 38.5, "lon": -98.3, "key": "kansas"},
        {"name": "Île-de-France",       "lat": 48.4, "lon":   2.5, "key": "paris"},
        {"name": "Odessa · Black Sea",  "lat": 46.5, "lon":  30.7, "key": "odessa"},
    ]

    NORMALS = {
        "iowa":   [-7,-5,1,9,16,21,24,23,17,9,1,-5],
        "kansas": [-1,2,8,14,19,25,29,28,22,14,6,0],
        "paris":  [4,4,8,11,15,18,21,20,17,12,7,4],
        "odessa": [0,1,5,11,17,22,24,24,19,13,6,1],
    }

    WC = {
        0:"Clear",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
        45:"Fog",51:"Lt drizzle",61:"Lt rain",63:"Rain",65:"Heavy rain",
        71:"Lt snow",73:"Snow",80:"Showers",95:"T-storm"
    }

    print(f"[{datetime.now():%H:%M:%S}] Fetching weather...")
    lats = ",".join(str(l["lat"]) for l in LOCATIONS)
    lons = ",".join(str(l["lon"]) for l in LOCATIONS)
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lats}&longitude={lons}"
        f"&current_weather=true"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&forecast_days=14&timezone=auto"
    )

    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            raw = json.loads(r.read())
        arr = raw if isinstance(raw, list) else [raw]

        weather = []
        for i, d in enumerate(arr):
            loc  = LOCATIONS[i]
            cw   = d.get("current_weather", {})
            dy   = d.get("daily", {})
            mo   = datetime.now().month - 1
            norm = NORMALS[loc["key"]][mo]

            forecast = []
            for j, t in enumerate(dy.get("time", [])):
                mo2   = int(t[5:7]) - 1
                norm2 = NORMALS[loc["key"]][mo2]
                forecast.append({
                    "date":   t,
                    "hi":     dy["temperature_2m_max"][j],
                    "lo":     dy["temperature_2m_min"][j],
                    "precip": dy["precipitation_sum"][j],
                    "code":   dy["weathercode"][j],
                    "norm":   norm2,
                })

            weather.append({
                "name":        loc["name"],
                "key":         loc["key"],
                "current_temp": cw.get("temperature"),
                "current_code": cw.get("weathercode"),
                "current_desc": WC.get(cw.get("weathercode", 0), ""),
                "norm":        norm,
                "forecast":    forecast,
            })
            print(f"  ✓ {loc['name']:<25} {cw.get('temperature','?')}°C  {WC.get(cw.get('weathercode',0),'')}")
        return weather

    except Exception as e:
        print(f"  ✗ Weather ERROR: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="GrainBrief data fetcher")
    parser.add_argument("--loop", action="store_true", help="Refresh every 10 minutes")
    parser.add_argument("--interval", type=int, default=600, help="Seconds between refreshes (default 600)")
    args = parser.parse_args()

    def run_once():
        data = {
            "fetched_at":  datetime.now().isoformat(),
            "contracts":   CONTRACTS,
            "prices":      fetch_prices(),
            "weather":     fetch_weather(),
        }
        OUTPUT.write_text(json.dumps(data, indent=2))
        print(f"[{datetime.now():%H:%M:%S}] ✓ Written to {OUTPUT}")
        print("-" * 50)

    run_once()

    if args.loop:
        print(f"Looping every {args.interval}s — press Ctrl+C to stop\n")
        while True:
            time.sleep(args.interval)
            run_once()


if __name__ == "__main__":
    main()
