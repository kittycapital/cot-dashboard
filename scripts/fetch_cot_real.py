#!/usr/bin/env python3
"""
CFTC COT Data Fetcher
- Downloads historical and current COT data from CFTC
- Parses Legacy Report format
- Extracts data for target futures contracts
- No API key needed — government public data

Usage:
  python fetch_cot_real.py --initial    # Download 10 years of bulk data
  python fetch_cot_real.py --update     # Download latest week only
"""

import os
import sys
import csv
import json
import zipfile
import io
import argparse
from datetime import datetime, timedelta

# Check for required packages
try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests --break-system-packages -q")
    import requests

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    os.system(f"{sys.executable} -m pip install yfinance --break-system-packages -q")
    import yfinance as yf

# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# CFTC Legacy Futures-Only Report URLs
# Annual files: https://www.cftc.gov/files/dea/history/deacot{YEAR}.zip
# Current year: https://www.cftc.gov/files/dea/history/deacot{YEAR}.zip
CFTC_BASE_URL = "https://www.cftc.gov/files/dea/history"

# Contract name patterns in CFTC data (partial match)
CONTRACT_MAP = {
    "BTC":     {"pattern": "BITCOIN", "exchange": "CHICAGO MERCANTILE EXCHANGE"},
    "ETH":     {"pattern": "ETHER",   "exchange": "CHICAGO MERCANTILE EXCHANGE"},
    "SP500":   {"pattern": "E-MINI S&P 500",     "exchange": "CHICAGO MERCANTILE EXCHANGE"},
    "NASDAQ":  {"pattern": "NASDAQ-100",          "exchange": "CHICAGO MERCANTILE EXCHANGE"},
    "RUSSELL": {"pattern": "E-MINI RUSSELL 2000", "exchange": "CHICAGO MERCANTILE EXCHANGE"},
    "DXY":     {"pattern": "U.S. DOLLAR INDEX",   "exchange": "ICE FUTURES U.S."},
    "GOLD":    {"pattern": "GOLD",                 "exchange": "COMMODITY EXCHANGE INC."},
    "SILVER":  {"pattern": "SILVER",               "exchange": "COMMODITY EXCHANGE INC."},
    "COPPER":  {"pattern": "COPPER",               "exchange": "COMMODITY EXCHANGE INC."},
    "OIL":     {"pattern": "CRUDE OIL, LIGHT SWEET", "exchange": "NEW YORK MERCANTILE EXCHANGE"},
}

# yfinance tickers for price data
PRICE_TICKERS = {
    "BTC":     "BTC-USD",
    "ETH":     "ETH-USD",
    "SP500":   "^GSPC",
    "NASDAQ":  "^IXIC",
    "RUSSELL": "^RUT",
    "DXY":     "DX-Y.NYB",
    "GOLD":    "GC=F",
    "SILVER":  "SI=F",
    "COPPER":  "HG=F",
    "OIL":     "CL=F",
}

ASSET_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SP500": "S&P 500",
    "NASDAQ": "Nasdaq 100", "RUSSELL": "Russell 2000", "DXY": "US Dollar Index",
    "GOLD": "Gold", "SILVER": "Silver", "COPPER": "Copper", "OIL": "Crude Oil WTI"
}

Z_WINDOW = 156   # 3 years
Z_THRESHOLD = 1.8
PCT_HIGH = 90
PCT_LOW = 10

# ============================================================
# CFTC DATA DOWNLOAD
# ============================================================

def download_cftc_year(year):
    """Download and parse one year of CFTC Legacy Report data"""
    url = f"{CFTC_BASE_URL}/deacot{year}.zip"
    print(f"  Downloading {url}...")
    
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        print(f"  Warning: Could not download {year} (status {resp.status_code})")
        return []
    
    # Extract CSV from zip
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    csv_name = z.namelist()[0]
    csv_data = z.read(csv_name).decode('utf-8', errors='replace')
    
    reader = csv.DictReader(io.StringIO(csv_data))
    rows = list(reader)
    print(f"  {year}: {len(rows)} total rows")
    return rows


def parse_cftc_rows(rows):
    """Extract relevant contracts from raw CFTC rows"""
    results = {key: [] for key in CONTRACT_MAP}
    
    for row in rows:
        market_name = row.get('Market_and_Exchange_Names', '').upper()
        
        for key, config in CONTRACT_MAP.items():
            pattern = config['pattern'].upper()
            exchange = config['exchange'].upper()
            
            if pattern in market_name and exchange in market_name:
                try:
                    # Parse date: YYMMDD or YYYY-MM-DD format
                    date_str = row.get('As_of_Date_In_Form_YYMMDD', '')
                    if len(date_str) == 6:
                        # YYMMDD format
                        yy = int(date_str[:2])
                        year = 2000 + yy if yy < 80 else 1900 + yy
                        month = int(date_str[2:4])
                        day = int(date_str[4:6])
                        date = f"{year}-{month:02d}-{day:02d}"
                    else:
                        date = row.get('Report_Date_as_YYYY-MM-DD', date_str)
                    
                    entry = {
                        "date": date,
                        "open_interest": int(row.get('Open_Interest_All', 0)),
                        "noncommercial_long": int(row.get('NonComm_Positions_Long_All', 0)),
                        "noncommercial_short": int(row.get('NonComm_Positions_Short_All', 0)),
                        "commercial_long": int(row.get('Comm_Positions_Long_All', 0)),
                        "commercial_short": int(row.get('Comm_Positions_Short_All', 0)),
                    }
                    results[key].append(entry)
                except (ValueError, KeyError) as e:
                    continue
                break  # Found match, move to next row
    
    # Sort by date
    for key in results:
        results[key].sort(key=lambda x: x['date'])
    
    return results


def download_all_cot(start_year=2015):
    """Download all years of CFTC data"""
    current_year = datetime.now().year
    all_rows = []
    
    for year in range(start_year, current_year + 1):
        rows = download_cftc_year(year)
        all_rows.extend(rows)
    
    return parse_cftc_rows(all_rows)


def download_latest_cot():
    """Download only current year's data"""
    year = datetime.now().year
    rows = download_cftc_year(year)
    return parse_cftc_rows(rows)


# ============================================================
# PRICE DATA
# ============================================================

def fetch_prices(start_date="2015-01-01"):
    """Fetch weekly price data for all assets via yfinance"""
    prices = {}
    
    for key, ticker in PRICE_TICKERS.items():
        print(f"  Fetching {key} ({ticker})...")
        try:
            df = yf.download(ticker, start=start_date, interval="1wk", progress=False)
            
            # Handle multi-level columns (newer yfinance versions)
            if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)
            
            if len(df) > 0:
                price_data = []
                close_col = df['Close']
                for idx in df.index:
                    date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
                    val = close_col.loc[idx]
                    # Handle Series vs scalar
                    if hasattr(val, 'iloc'):
                        val = val.iloc[0]
                    price_data.append({
                        "date": date_str,
                        "price": round(float(val), 2)
                    })
                prices[key] = price_data
                print(f"    {key}: {len(price_data)} weekly prices")
            else:
                print(f"    {key}: No data returned")
                prices[key] = []
        except Exception as e:
            print(f"    {key}: Error - {e}")
            prices[key] = []
    
    return prices


def merge_price_csv(prices, key, csv_path):
    """Merge uploaded CSV price data with yfinance data"""
    if not os.path.exists(csv_path):
        return prices
    
    csv_prices = {}
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row['Date'].strip()
            csv_prices[date] = round(float(row['Close']), 2)
    
    # Merge: CSV takes priority for overlapping dates
    existing_dates = {p['date'] for p in prices.get(key, [])}
    merged = list(prices.get(key, []))
    
    for date, price in csv_prices.items():
        if date not in existing_dates:
            merged.append({"date": date, "price": price})
    
    merged.sort(key=lambda x: x['date'])
    prices[key] = merged
    print(f"  Merged CSV for {key}: {len(merged)} total prices")
    return prices


# ============================================================
# SIGNAL CALCULATION
# ============================================================

def calculate_signals(cot_data):
    """Calculate Z-Score, percentile, and spread signals"""
    results = []
    
    for i, row in enumerate(cot_data):
        comm_net = row["commercial_long"] - row["commercial_short"]
        noncomm_net = row["noncommercial_long"] - row["noncommercial_short"]
        spread = comm_net - noncomm_net
        oi = row["open_interest"]
        noncomm_long_pct = (row["noncommercial_long"] / oi * 100) if oi > 0 else 0
        
        # Rolling window
        ws = max(0, i - Z_WINDOW + 1)
        
        # Z-Score of commercial net
        nets = [cot_data[j]["commercial_long"] - cot_data[j]["commercial_short"] for j in range(ws, i+1)]
        if len(nets) >= 20:
            mean_n = sum(nets) / len(nets)
            std_n = (sum((x - mean_n)**2 for x in nets) / len(nets)) ** 0.5
            z = round((comm_net - mean_n) / std_n, 2) if std_n > 0 else 0
        else:
            z = 0
        
        # Percentile of non-comm long % OI
        pcts = []
        for j in range(ws, i+1):
            oi_j = cot_data[j]["open_interest"]
            if oi_j > 0:
                pcts.append(cot_data[j]["noncommercial_long"] / oi_j * 100)
        if len(pcts) >= 20:
            rank = sum(1 for x in sorted(pcts) if x <= noncomm_long_pct)
            percentile = round(rank / len(pcts) * 100, 1)
        else:
            percentile = 50
        
        # Spread Z-Score
        spreads = [
            (cot_data[j]["commercial_long"] - cot_data[j]["commercial_short"]) -
            (cot_data[j]["noncommercial_long"] - cot_data[j]["noncommercial_short"])
            for j in range(ws, i+1)
        ]
        if len(spreads) >= 20:
            mean_s = sum(spreads) / len(spreads)
            std_s = (sum((x - mean_s)**2 for x in spreads) / len(spreads)) ** 0.5
            spread_z = round((spread - mean_s) / std_s, 2) if std_s > 0 else 0
        else:
            spread_z = 0
        
        z_sig = "bullish" if z > Z_THRESHOLD else ("bearish" if z < -Z_THRESHOLD else None)
        pct_sig = "bearish" if percentile > PCT_HIGH else ("bullish" if percentile < PCT_LOW else None)
        sp_sig = "bullish" if spread_z > Z_THRESHOLD else ("bearish" if spread_z < -Z_THRESHOLD else None)
        
        results.append({
            "date": row["date"],
            "commercial_net": comm_net,
            "noncommercial_net": noncomm_net,
            "noncomm_long_pct_oi": round(noncomm_long_pct, 2),
            "spread": spread,
            "z_score": z,
            "percentile": percentile,
            "spread_z": spread_z,
            "z_signal": z_sig,
            "pct_signal": pct_sig,
            "spread_signal": sp_sig,
        })
    
    return results


def build_signal_history(prices_list, signals, lookahead=[4, 8, 13, 26]):
    """Calculate returns after each signal"""
    history = []
    
    for i, sig in enumerate(signals):
        for stype, skey in [("z_score", "z_signal"), ("pct_oi", "pct_signal"), ("spread", "spread_signal")]:
            if sig[skey] is not None and i < len(prices_list):
                entry = {
                    "date": sig["date"],
                    "type": stype,
                    "direction": sig[skey],
                    "price_at_signal": prices_list[i],
                    "z_score": sig["z_score"],
                    "percentile": sig["percentile"],
                    "spread_z": sig["spread_z"],
                    "returns": {}
                }
                for w in lookahead:
                    fi = i + w
                    if fi < len(prices_list):
                        ret = round((prices_list[fi] - prices_list[i]) / prices_list[i] * 100, 2)
                        entry["returns"][f"{w}w"] = ret
                    else:
                        entry["returns"][f"{w}w"] = None
                history.append(entry)
    
    return history


# ============================================================
# MERGE COT + PRICES → FINAL JSON
# ============================================================

def build_dashboard_data(cot_all, prices_all):
    """Combine COT and price data into dashboard format"""
    result = {}
    
    for key in CONTRACT_MAP:
        cot_data = cot_all.get(key, [])
        price_data = prices_all.get(key, [])
        
        if not cot_data:
            print(f"  {key}: No COT data, skipping")
            continue
        
        # Build price lookup
        price_map = {p["date"]: p["price"] for p in price_data}
        
        # Align prices with COT dates (find nearest)
        aligned_prices = []
        price_dates = sorted(price_map.keys())
        
        for cot_row in cot_data:
            cot_date = cot_row["date"]
            if cot_date in price_map:
                aligned_prices.append(price_map[cot_date])
            else:
                # Find nearest price within 7 days
                best = None
                best_diff = 999
                for pd in price_dates:
                    try:
                        diff = abs((datetime.strptime(pd, "%Y-%m-%d") - datetime.strptime(cot_date, "%Y-%m-%d")).days)
                        if diff < best_diff:
                            best_diff = diff
                            best = price_map[pd]
                    except:
                        continue
                aligned_prices.append(best if best else 0)
        
        # Fill zeros
        for i in range(len(aligned_prices)):
            if aligned_prices[i] == 0 and i > 0:
                aligned_prices[i] = aligned_prices[i-1]
        
        # Calculate signals
        signals = calculate_signals(cot_data)
        signal_history = build_signal_history(aligned_prices, signals)
        
        # Build merged weekly data
        weekly_data = []
        for i in range(len(cot_data)):
            weekly_data.append({
                "date": cot_data[i]["date"],
                "price": round(aligned_prices[i], 2) if i < len(aligned_prices) else 0,
                "open_interest": cot_data[i]["open_interest"],
                "commercial_long": cot_data[i]["commercial_long"],
                "commercial_short": cot_data[i]["commercial_short"],
                "noncommercial_long": cot_data[i]["noncommercial_long"],
                "noncommercial_short": cot_data[i]["noncommercial_short"],
                **signals[i],
            })
        
        result[key] = {
            "name": ASSET_NAMES[key],
            "ticker": PRICE_TICKERS[key],
            "cot_code": CONTRACT_MAP[key]["pattern"],
            "data": weekly_data,
            "signal_history": signal_history,
        }
        
        latest = weekly_data[-1] if weekly_data else {}
        print(f"  {key}: {len(weekly_data)} weeks, z={latest.get('z_score','-')}, pct={latest.get('percentile','-')}")
    
    return result


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="COT Dashboard Data Fetcher")
    parser.add_argument('--initial', action='store_true', help='Download 10 years of historical data')
    parser.add_argument('--update', action='store_true', help='Update with latest weekly data')
    parser.add_argument('--start-year', type=int, default=2015, help='Start year for initial download')
    parser.add_argument('--btc-csv', type=str, default=None, help='Path to BTC CSV file')
    parser.add_argument('--eth-csv', type=str, default=None, help='Path to ETH CSV file')
    args = parser.parse_args()
    
    if not args.initial and not args.update:
        print("Usage: python fetch_cot_real.py --initial  or  --update")
        sys.exit(1)
    
    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = os.path.join(DATA_DIR, "cot_dashboard_data.json")
    
    if args.initial:
        print("=== INITIAL LOAD: Downloading historical CFTC data ===")
        print(f"Years: {args.start_year} - {datetime.now().year}")
        cot_all = download_all_cot(start_year=args.start_year)
        
        for key in cot_all:
            print(f"  {key}: {len(cot_all[key])} COT records")
    
    elif args.update:
        print("=== WEEKLY UPDATE ===")
        # Load existing data
        if os.path.exists(output_path):
            with open(output_path, 'r') as f:
                existing = json.load(f)
        else:
            print("No existing data found. Run --initial first.")
            sys.exit(1)
        
        # Download latest
        latest_cot = download_latest_cot()
        
        # Merge with existing COT data
        cot_all = {}
        for key in CONTRACT_MAP:
            existing_dates = set()
            existing_cot = []
            if key in existing:
                for row in existing[key].get("data", []):
                    existing_dates.add(row["date"])
                    existing_cot.append({
                        "date": row["date"],
                        "open_interest": row["open_interest"],
                        "commercial_long": row["commercial_long"],
                        "commercial_short": row["commercial_short"],
                        "noncommercial_long": row["noncommercial_long"],
                        "noncommercial_short": row["noncommercial_short"],
                    })
            
            # Add new rows
            new_count = 0
            for row in latest_cot.get(key, []):
                if row["date"] not in existing_dates:
                    existing_cot.append(row)
                    new_count += 1
            
            existing_cot.sort(key=lambda x: x["date"])
            cot_all[key] = existing_cot
            print(f"  {key}: +{new_count} new records")
    
    # Fetch prices
    print("\n=== Fetching price data ===")
    prices_all = fetch_prices(start_date=f"{args.start_year if args.initial else datetime.now().year}-01-01")
    
    # Merge CSV files if provided
    if args.btc_csv:
        prices_all = merge_price_csv(prices_all, "BTC", args.btc_csv)
    if args.eth_csv:
        prices_all = merge_price_csv(prices_all, "ETH", args.eth_csv)
    
    # Build final dashboard data
    print("\n=== Building dashboard data ===")
    dashboard_data = build_dashboard_data(cot_all, prices_all)
    
    # Save
    with open(output_path, 'w') as f:
        json.dump(dashboard_data, f)
    
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"\nSaved to {output_path} ({size_mb:.1f} MB)")
    print("Done!")


if __name__ == "__main__":
    main()
