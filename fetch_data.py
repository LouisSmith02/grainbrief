#!/usr/bin/env python3
"""
GrainBrief Data Fetcher
=======================
Run this on your laptop to pull all market data and write data.json.

Install once:  pip install yfinance requests
Run manually:  python fetch_data.py
Auto-loop:     python fetch_data.py --loop
"""

import yfinance as yf
import json, time, argparse, sys
from datetime import datetime, date
from pathlib import Path
import urllib.request

OUTPUT = Path(__file__).parent / "data.json"

# ── CONTRACTS ─────────────────────────────────────────────────────────────────
# 5 forward contracts each for CBOT Corn and CBOT Wheat (SRW)
# MATIF not on Yahoo Finance - shown as manual reference
CONTRACTS = [
    {"sym": "ZCN26.CBT", "label": "Corn  Jul 26", "unit": "USc/bu", "cls": "corn",  "col": "#d3c149", "group": "CBOT Corn"},
    {"sym": "ZCZ26.CBT", "label": "Corn  Dec 26", "unit": "USc/bu", "cls": "corn",  "col": "#d3c149", "group": "CBOT Corn"},
    {"sym": "ZCH27.CBT", "label": "Corn  Mar 27", "unit": "USc/bu", "cls": "corn",  "col": "#d3c149", "group": "CBOT Corn"},
    {"sym": "ZCK27.CBT", "label": "Corn  May 27", "unit": "USc/bu", "cls": "corn",  "col": "#d3c149", "group": "CBOT Corn"},
    {"sym": "ZCN27.CBT", "label": "Corn  Jul 27", "unit": "USc/bu", "cls": "corn",  "col": "#d3c149", "group": "CBOT Corn"},

    {"sym": "ZWN26.CBT", "label": "Wheat Jul 26", "unit": "USc/bu", "cls": "wheat", "col": "#c79f44", "group": "CBOT Wheat SRW"},
    {"sym": "ZWU26.CBT", "label": "Wheat Sep 26", "unit": "USc/bu", "cls": "wheat", "col": "#c79f44", "group": "CBOT Wheat SRW"},
    {"sym": "ZWZ26.CBT", "label": "Wheat Dec 26", "unit": "USc/bu", "cls": "wheat", "col": "#c79f44", "group": "CBOT Wheat SRW"},
    {"sym": "ZWH27.CBT", "label": "Wheat Mar 27", "unit": "USc/bu", "cls": "wheat", "col": "#c79f44", "group": "CBOT Wheat SRW"},
    {"sym": "ZWK27.CBT", "label": "Wheat May 27", "unit": "USc/bu", "cls": "wheat", "col": "#c79f44", "group": "CBOT Wheat SRW"},

    # MATIF — not on Yahoo Finance; placeholder rows shown in dashboard
    {"sym": "MATIF_W",   "label": "Mill. Wheat",  "unit": "€/t",   "cls": "wheat", "col": "#e8b84b", "group": "MATIF (euronext.com)", "manual": True},
    {"sym": "MATIF_C",   "label": "Corn",          "unit": "€/t",   "cls": "corn",  "col": "#b8d44a", "group": "MATIF (euronext.com)", "manual": True},
]

YTD_SYMS = {"ZCN26.CBT", "ZWN26.CBT"}


# ── WEATHER SETTINGS ──────────────────────────────────────────────────────────
LOCATIONS = [
    {"name": "Iowa · Corn Belt",    "lat": 42.0, "lon": -93.6, "key": "iowa"},
    {"name": "Kansas · Wheat Belt", "lat": 38.5, "lon": -98.3, "key": "kansas"},
    {"name": "Île-de-France",       "lat": 48.4, "lon":   2.5, "key": "paris"},
    {"name": "Odessa · Black Sea",  "lat": 46.5, "lon":  30.7, "key": "odessa"},
]

# 30-year monthly climate normals (°C) Jan–Dec per region
NORMALS = {
    "iowa":   [-7, -5,  1,  9, 16, 21, 24, 23, 17,  9,  1, -5],
    "kansas": [-1,  2,  8, 14, 19, 25, 29, 28, 22, 14,  6,  0],
    "paris":  [ 4,  4,  8, 11, 15, 18, 21, 20, 17, 12,  7,  4],
    "odessa": [ 0,  1,  5, 11, 17, 22, 24, 24, 19, 13,  6,  1],
}

WC = {
    0:"Clear", 1:"Mainly clear", 2:"Partly cloudy", 3:"Overcast",
    45:"Fog", 48:"Icy fog", 51:"Lt drizzle", 53:"Drizzle", 55:"Hvy drizzle",
    61:"Lt rain", 63:"Rain", 65:"Heavy rain",
    71:"Lt snow", 73:"Snow", 75:"Heavy snow",
    80:"Showers", 81:"Showers", 82:"Heavy showers",
    95:"T-storm", 99:"T-storm+hail",
}


# ── FETCH PRICES ──────────────────────────────────────────────────────────────
def fetch_prices():
    print(f"[{datetime.now():%H:%M:%S}] Fetching prices...")
    prices = {}
    for c in CONTRACTS:
        if c.get("manual"):
            continue  # skip MATIF placeholders
        sym = c["sym"]
        try:
            tk   = yf.Ticker(sym)
            info = tk.fast_info
            price = float(info.last_price)
            prev  = float(info.previous_close)
            hi    = float(info.day_high)
            lo    = float(info.day_low)

            ytd_closes, ytd_dates = [], []
            if sym in YTD_SYMS:
                hist = tk.history(start=f"{date.today().year}-01-01", interval="1d", auto_adjust=True)
                if not hist.empty:
                    ytd_closes = [round(float(v), 4) for v in hist["Close"].dropna()]
                    ytd_dates  = [str(d.date()) for d in hist.index]

            prices[sym] = {
                "price":      round(price, 4),
                "prev":       round(prev, 4),
                "hi":         round(hi, 4),
                "lo":         round(lo, 4),
                "change":     round(price - prev, 4),
                "pct":        round(((price - prev) / prev) * 100, 4),
                "ytd_closes": ytd_closes,
                "ytd_dates":  ytd_dates,
            }
            sign = "+" if price >= prev else ""
            print(f"  ✓ {sym:<14} {price:>8.2f}  ({sign}{price-prev:.2f})")

        except Exception as e:
            print(f"  ✗ {sym:<14} ERROR: {e}")
            prices[sym] = None

    return prices


# ── FETCH WEATHER ─────────────────────────────────────────────────────────────
def fetch_weather():
    print(f"[{datetime.now():%H:%M:%S}] Fetching 14-day weather forecast...")
    lats = ",".join(str(l["lat"]) for l in LOCATIONS)
    lons = ",".join(str(l["lon"]) for l in LOCATIONS)
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lats}&longitude={lons}"
        "&current_weather=true"
        "&daily=weathercode,temperature_2m_max,temperature_2m_min,"
        "precipitation_sum,windspeed_10m_max,precipitation_probability_max"
        "&forecast_days=14&timezone=auto"
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
                    "date":     t,
                    "hi":       dy["temperature_2m_max"][j],
                    "lo":       dy["temperature_2m_min"][j],
                    "precip":   dy["precipitation_sum"][j],
                    "precip_prob": dy.get("precipitation_probability_max", [None]*14)[j],
                    "wind_max": dy.get("windspeed_10m_max", [None]*14)[j],
                    "code":     dy["weathercode"][j],
                    "desc":     WC.get(dy["weathercode"][j], ""),
                    "norm":     norm2,
                })

            weather.append({
                "name":         loc["name"],
                "key":          loc["key"],
                "current_temp": cw.get("temperature"),
                "current_code": cw.get("weathercode"),
                "current_desc": WC.get(cw.get("weathercode", 0), ""),
                "current_wind": cw.get("windspeed"),
                "norm":         norm,
                "forecast":     forecast,
            })
            print(f"  ✓ {loc['name']:<25} {cw.get('temperature','?')}°C  "
                  f"{WC.get(cw.get('weathercode', 0), '')}  "
                  f"wind {cw.get('windspeed','?')} km/h")
        return weather

    except Exception as e:
        print(f"  ✗ Weather ERROR: {e}")
        return []


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop",     action="store_true")
    parser.add_argument("--interval", type=int, default=600)
    args = parser.parse_args()

    def run_once():
        data = {
            "fetched_at": datetime.now().isoformat(),
            "contracts":  CONTRACTS,
            "prices":     fetch_prices(),
            "weather":    fetch_weather(),
        }
        OUTPUT.write_text(json.dumps(data, indent=2))
        print(f"[{datetime.now():%H:%M:%S}] ✓ Written to {OUTPUT}")
        print("-" * 50)

    run_once()
    if args.loop:
        print(f"Looping every {args.interval//60} min — Ctrl+C to stop\n")
        while True:
            time.sleep(args.interval)
            run_once()

if __name__ == "__main__":
    main()
