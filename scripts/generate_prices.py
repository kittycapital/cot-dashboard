#!/usr/bin/env python3
"""
COT Dashboard — Daily Price Generator
Downloads daily price history for all COT assets from Yahoo Finance.
Saves as data/prices.json (compact format: {ASSET: [{d, p}, ...]}).

Usage:
  python scripts/generate_prices.py
  python scripts/generate_prices.py --start-year 2017
"""
import os, sys, json, argparse
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    os.system(f"{sys.executable} -m pip install yfinance --break-system-packages -q")
    import yfinance as yf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")

TICKER_MAP = {
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SP500": "^GSPC",
    "NASDAQ": "^NDX", "RUSSELL": "^RUT", "DXY": "DX-Y.NYB",
    "GOLD": "GC=F", "SILVER": "SI=F", "COPPER": "HG=F", "OIL": "CL=F",
}


def download_daily(key, ticker, start):
    print(f"  {key} ({ticker})...", end=" ", flush=True)
    try:
        df = yf.download(ticker, start=start, interval="1d", progress=False)
        if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            print("no data")
            return []
        rows = []
        for idx, row in df.iterrows():
            try:
                val = row["Close"]
                if hasattr(val, 'iloc'): val = val.iloc[0]
                if hasattr(val, 'item'): val = val.item()
                val = float(val)
                if val > 0:
                    rows.append({"d": idx.strftime("%Y-%m-%d"), "p": round(val, 2)})
            except:
                continue
        print(f"{len(rows)} days ({rows[0]['d']} → {rows[-1]['d']})")
        return rows
    except Exception as e:
        print(f"error: {e}")
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-year', type=int, default=2015)
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    start = f"{args.start_year}-01-01"
    print(f"=== Generating daily prices from {start} ===")

    result = {}
    for key, ticker in TICKER_MAP.items():
        rows = download_daily(key, ticker, start)
        if rows:
            result[key] = rows

    out = os.path.join(DATA_DIR, "prices.json")
    with open(out, "w") as f:
        json.dump(result, f, separators=(",", ":"))

    mb = os.path.getsize(out) / 1024 / 1024
    print(f"\n✅ Saved: {out} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
