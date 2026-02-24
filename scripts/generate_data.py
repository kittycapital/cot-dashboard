#!/usr/bin/env python3
"""
COT Dashboard Data Generator
- Generates realistic sample COT data for demo
- Processes uploaded BTC/ETH CSV files for price data
- Calculates Z-Score, % OI, Spread signals
"""

import json
import csv
import math
import random
import os
from datetime import datetime, timedelta

# ============================================================
# CONFIGURATION
# ============================================================

ASSETS = {
    "BTC": {"name": "Bitcoin", "cot_code": "BITCOIN", "yf_ticker": "BTC-USD", "cot_start": 2017},
    "ETH": {"name": "Ethereum", "cot_code": "ETHER", "yf_ticker": "ETH-USD", "cot_start": 2021},
    "SP500": {"name": "S&P 500", "cot_code": "E-MINI S&P 500", "yf_ticker": "^GSPC", "cot_start": 2015},
    "NASDAQ": {"name": "Nasdaq 100", "cot_code": "E-MINI NASDAQ", "yf_ticker": "^IXIC", "cot_start": 2015},
    "RUSSELL": {"name": "Russell 2000", "cot_code": "E-MINI RUSSELL 2000", "yf_ticker": "^RUT", "cot_start": 2015},
    "DXY": {"name": "US Dollar Index", "cot_code": "U.S. DOLLAR INDEX", "yf_ticker": "DX-Y.NYB", "cot_start": 2015},
    "GOLD": {"name": "Gold", "cot_code": "GOLD", "yf_ticker": "GC=F", "cot_start": 2015},
    "SILVER": {"name": "Silver", "cot_code": "SILVER", "yf_ticker": "SI=F", "cot_start": 2015},
    "COPPER": {"name": "Copper", "cot_code": "COPPER", "yf_ticker": "HG=F", "cot_start": 2015},
    "OIL": {"name": "Crude Oil WTI", "cot_code": "CRUDE OIL", "yf_ticker": "CL=F", "cot_start": 2015},
}

Z_SCORE_WINDOW = 156  # 3 years in weeks
SIGNAL_THRESHOLD_Z = 1.8
SIGNAL_THRESHOLD_PCT_HIGH = 90
SIGNAL_THRESHOLD_PCT_LOW = 10

# ============================================================
# SAMPLE DATA GENERATION (for demo)
# ============================================================

def generate_sample_price(asset_key, weeks):
    """Generate realistic price series"""
    random.seed(hash(asset_key) % 2**31)
    
    base_prices = {
        "BTC": (400, 95000, 0.003), "ETH": (10, 3200, 0.003),
        "SP500": (2000, 6000, 0.001), "NASDAQ": (4500, 19000, 0.001),
        "RUSSELL": (1000, 2300, 0.001), "DXY": (88, 110, 0.0005),
        "GOLD": (1050, 2800, 0.001), "SILVER": (14, 32, 0.0015),
        "COPPER": (2.0, 4.8, 0.001), "OIL": (25, 85, 0.002),
    }
    
    start_p, end_p, vol = base_prices[asset_key]
    prices = []
    p = start_p
    trend = (end_p / start_p) ** (1.0 / weeks)
    
    for i in range(weeks):
        p *= trend * (1 + random.gauss(0, vol * 7))
        # Add some cycles
        cycle = 1 + 0.15 * math.sin(2 * math.pi * i / 104)  # ~2yr cycle
        cycle2 = 1 + 0.08 * math.sin(2 * math.pi * i / 52)  # ~1yr cycle
        prices.append(round(max(p * cycle * cycle2, start_p * 0.5), 2))
    
    return prices


def generate_sample_cot(asset_key, weeks, prices):
    """Generate realistic COT data correlated with price movements"""
    random.seed(hash(asset_key + "_cot") % 2**31)
    
    # Base OI scales
    oi_scales = {
        "BTC": (8000, 25000), "ETH": (3000, 15000),
        "SP500": (2000000, 3500000), "NASDAQ": (200000, 400000),
        "RUSSELL": (300000, 600000), "DXY": (30000, 70000),
        "GOLD": (400000, 700000), "SILVER": (150000, 250000),
        "COPPER": (150000, 300000), "OIL": (1500000, 2500000),
    }
    
    oi_min, oi_max = oi_scales[asset_key]
    cot_data = []
    
    # Track momentum for commercial positioning
    prev_comm_net = 0
    
    for i in range(weeks):
        # Open Interest with trend
        oi_trend = oi_min + (oi_max - oi_min) * (i / weeks)
        oi = int(oi_trend * (1 + 0.15 * math.sin(2 * math.pi * i / 78) + random.gauss(0, 0.05)))
        oi = max(oi, oi_min // 2)
        
        # Price momentum (commercials tend to be contrarian)
        if i > 10:
            price_mom = (prices[i] - prices[i-10]) / prices[i-10]
        else:
            price_mom = 0
        
        # Commercial positioning: contrarian to price (negative correlation)
        comm_bias = -price_mom * 0.4 + random.gauss(0, 0.05)
        comm_long_pct = 0.3 + comm_bias * 0.5 + 0.05 * math.sin(2 * math.pi * i / 130)
        comm_long_pct = max(0.15, min(0.50, comm_long_pct))
        comm_short_pct = 0.35 - comm_bias * 0.3 + 0.04 * math.sin(2 * math.pi * i / 90)
        comm_short_pct = max(0.15, min(0.50, comm_short_pct))
        
        # Non-commercial: trend following (positive correlation)
        noncomm_bias = price_mom * 0.3 + random.gauss(0, 0.04)
        noncomm_long_pct = 0.25 + noncomm_bias * 0.4 + 0.04 * math.sin(2 * math.pi * i / 65)
        noncomm_long_pct = max(0.10, min(0.45, noncomm_long_pct))
        noncomm_short_pct = 0.15 - noncomm_bias * 0.2 + 0.03 * math.sin(2 * math.pi * i / 80)
        noncomm_short_pct = max(0.05, min(0.35, noncomm_short_pct))
        
        comm_long = int(oi * comm_long_pct)
        comm_short = int(oi * comm_short_pct)
        noncomm_long = int(oi * noncomm_long_pct)
        noncomm_short = int(oi * noncomm_short_pct)
        
        cot_data.append({
            "open_interest": oi,
            "commercial_long": comm_long,
            "commercial_short": comm_short,
            "noncommercial_long": noncomm_long,
            "noncommercial_short": noncomm_short,
        })
    
    return cot_data


def calculate_signals(cot_data, z_window=Z_SCORE_WINDOW):
    """Calculate Z-Score, % OI percentile, and Spread signals"""
    results = []
    
    for i, row in enumerate(cot_data):
        comm_net = row["commercial_long"] - row["commercial_short"]
        noncomm_net = row["noncommercial_long"] - row["noncommercial_short"]
        spread = comm_net - noncomm_net
        oi = row["open_interest"]
        
        noncomm_long_pct_oi = (row["noncommercial_long"] / oi * 100) if oi > 0 else 0
        
        # Z-Score (rolling window)
        window_start = max(0, i - z_window + 1)
        window_nets = [cot_data[j]["commercial_long"] - cot_data[j]["commercial_short"] for j in range(window_start, i + 1)]
        
        if len(window_nets) >= 20:
            mean_net = sum(window_nets) / len(window_nets)
            std_net = (sum((x - mean_net) ** 2 for x in window_nets) / len(window_nets)) ** 0.5
            z_score = round((comm_net - mean_net) / std_net, 2) if std_net > 0 else 0
        else:
            z_score = 0
        
        # Percentile of Non-Commercial Long % OI (rolling window)
        window_pcts = []
        for j in range(window_start, i + 1):
            oi_j = cot_data[j]["open_interest"]
            if oi_j > 0:
                window_pcts.append(cot_data[j]["noncommercial_long"] / oi_j * 100)
        
        if len(window_pcts) >= 20:
            sorted_pcts = sorted(window_pcts)
            rank = sum(1 for x in sorted_pcts if x <= noncomm_long_pct_oi)
            percentile = round(rank / len(sorted_pcts) * 100, 1)
        else:
            percentile = 50
        
        # Spread Z-Score
        window_spreads = []
        for j in range(window_start, i + 1):
            cn = cot_data[j]["commercial_long"] - cot_data[j]["commercial_short"]
            ncn = cot_data[j]["noncommercial_long"] - cot_data[j]["noncommercial_short"]
            window_spreads.append(cn - ncn)
        
        if len(window_spreads) >= 20:
            mean_sp = sum(window_spreads) / len(window_spreads)
            std_sp = (sum((x - mean_sp) ** 2 for x in window_spreads) / len(window_spreads)) ** 0.5
            spread_z = round((spread - mean_sp) / std_sp, 2) if std_sp > 0 else 0
        else:
            spread_z = 0
        
        # Signals
        z_signal = "bullish" if z_score > SIGNAL_THRESHOLD_Z else ("bearish" if z_score < -SIGNAL_THRESHOLD_Z else None)
        pct_signal = "bearish" if percentile > SIGNAL_THRESHOLD_PCT_HIGH else ("bullish" if percentile < SIGNAL_THRESHOLD_PCT_LOW else None)
        spread_signal = "bullish" if spread_z > SIGNAL_THRESHOLD_Z else ("bearish" if spread_z < -SIGNAL_THRESHOLD_Z else None)
        
        results.append({
            "commercial_net": comm_net,
            "noncommercial_net": noncomm_net,
            "noncomm_long_pct_oi": round(noncomm_long_pct_oi, 2),
            "spread": spread,
            "z_score": z_score,
            "percentile": percentile,
            "spread_z": spread_z,
            "z_signal": z_signal,
            "pct_signal": pct_signal,
            "spread_signal": spread_signal,
        })
    
    return results


def calculate_signal_returns(prices, signals, dates, lookahead_weeks=[4, 8, 13, 26]):
    """Calculate returns after each signal for signal history"""
    history = []
    
    for i, sig in enumerate(signals):
        for sig_type, sig_key in [("z_score", "z_signal"), ("pct_oi", "pct_signal"), ("spread", "spread_signal")]:
            if sig[sig_key] is not None:
                entry = {
                    "date": dates[i],
                    "type": sig_type,
                    "direction": sig[sig_key],
                    "price_at_signal": prices[i],
                    "z_score": sig["z_score"],
                    "percentile": sig["percentile"],
                    "spread_z": sig["spread_z"],
                    "returns": {}
                }
                
                for weeks in lookahead_weeks:
                    future_idx = i + weeks
                    if future_idx < len(prices):
                        ret = round((prices[future_idx] - prices[i]) / prices[i] * 100, 2)
                        entry["returns"][f"{weeks}w"] = ret
                    else:
                        entry["returns"][f"{weeks}w"] = None
                
                history.append(entry)
    
    return history


def load_csv_prices(filepath):
    """Load price data from uploaded CSV"""
    dates = []
    prices = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates.append(row['Date'].strip())
            prices.append(float(row['Close']))
    return dates, prices


def weekly_sample(dates, prices):
    """Convert daily prices to weekly (Friday close)"""
    weekly_dates = []
    weekly_prices = []
    
    for i, (d, p) in enumerate(zip(dates, prices)):
        dt = datetime.strptime(d, "%Y-%m-%d")
        # Take every Tuesday's data (COT report date)
        if dt.weekday() == 1:  # Tuesday
            weekly_dates.append(d)
            weekly_prices.append(p)
    
    # If no Tuesdays, just sample weekly
    if not weekly_dates:
        for i in range(0, len(dates), 7):
            weekly_dates.append(dates[i])
            weekly_prices.append(prices[i])
    
    return weekly_dates, weekly_prices


def generate_all_data(btc_csv=None, eth_csv=None):
    """Generate complete dataset for all assets"""
    
    # Date range: ~10 years of weekly data
    start_date = datetime(2015, 6, 1)
    end_date = datetime(2026, 2, 4)
    
    all_data = {}
    
    for key, config in ASSETS.items():
        cot_start = datetime(config["cot_start"], 1, 1)
        actual_start = max(start_date, cot_start)
        
        # Generate weekly dates (Tuesdays)
        dates = []
        d = actual_start
        while d.weekday() != 1:  # Find first Tuesday
            d += timedelta(days=1)
        while d <= end_date:
            dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=7)
        
        weeks = len(dates)
        
        # Price data: use CSV if available, otherwise generate
        if key == "BTC" and btc_csv:
            csv_dates, csv_prices = load_csv_prices(btc_csv)
            w_dates, w_prices = weekly_sample(csv_dates, csv_prices)
            # Align with COT dates
            price_map = dict(zip(w_dates, w_prices))
            prices = []
            for dt in dates:
                # Find closest price
                if dt in price_map:
                    prices.append(price_map[dt])
                else:
                    # Find nearest
                    dt_obj = datetime.strptime(dt, "%Y-%m-%d")
                    closest = None
                    min_diff = 999
                    for wd, wp in zip(w_dates, w_prices):
                        diff = abs((datetime.strptime(wd, "%Y-%m-%d") - dt_obj).days)
                        if diff < min_diff:
                            min_diff = diff
                            closest = wp
                    prices.append(closest if closest else 0)
            # Fill any remaining zeros
            for i in range(len(prices)):
                if prices[i] == 0 and i > 0:
                    prices[i] = prices[i-1]
        elif key == "ETH" and eth_csv:
            csv_dates, csv_prices = load_csv_prices(eth_csv)
            w_dates, w_prices = weekly_sample(csv_dates, csv_prices)
            price_map = dict(zip(w_dates, w_prices))
            prices = []
            for dt in dates:
                if dt in price_map:
                    prices.append(price_map[dt])
                else:
                    dt_obj = datetime.strptime(dt, "%Y-%m-%d")
                    closest = None
                    min_diff = 999
                    for wd, wp in zip(w_dates, w_prices):
                        diff = abs((datetime.strptime(wd, "%Y-%m-%d") - dt_obj).days)
                        if diff < min_diff:
                            min_diff = diff
                            closest = wp
                    prices.append(closest if closest else 0)
            for i in range(len(prices)):
                if prices[i] == 0 and i > 0:
                    prices[i] = prices[i-1]
        else:
            prices = generate_sample_price(key, weeks)
        
        # COT data
        cot_raw = generate_sample_cot(key, weeks, prices)
        signals = calculate_signals(cot_raw)
        signal_history = calculate_signal_returns(prices, signals, dates)
        
        # Merge into final structure
        weekly_data = []
        for i in range(weeks):
            weekly_data.append({
                "date": dates[i],
                "price": round(prices[i], 2),
                **cot_raw[i],
                **signals[i],
            })
        
        all_data[key] = {
            "name": config["name"],
            "ticker": config["yf_ticker"],
            "cot_code": config["cot_code"],
            "data": weekly_data,
            "signal_history": signal_history,
        }
        
        print(f"  {key}: {weeks} weeks, {len(signal_history)} signals generated")
    
    return all_data


if __name__ == "__main__":
    print("Generating COT Dashboard data...")
    
    # Check for uploaded CSV files
    btc_csv = None
    eth_csv = None
    
    for path in ["/mnt/user-data/uploads/BTC_USD.csv", "data/BTC_USD.csv", "../data/BTC_USD.csv"]:
        if os.path.exists(path):
            btc_csv = path
            print(f"  Found BTC CSV: {path}")
            break
    
    for path in ["/mnt/user-data/uploads/ETH_USD.csv", "data/ETH_USD.csv", "../data/ETH_USD.csv"]:
        if os.path.exists(path):
            eth_csv = path
            print(f"  Found ETH CSV: {path}")
            break
    
    all_data = generate_all_data(btc_csv=btc_csv, eth_csv=eth_csv)
    
    # Save to JSON
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "cot_dashboard_data.json")
    with open(output_path, 'w') as f:
        json.dump(all_data, f)
    
    # Print summary
    total_size = os.path.getsize(output_path)
    print(f"\nSaved to {output_path} ({total_size / 1024 / 1024:.1f} MB)")
    
    for key in all_data:
        d = all_data[key]
        latest = d["data"][-1]
        print(f"  {key}: price=${latest['price']}, z={latest['z_score']}, pct={latest['percentile']}, spread_z={latest['spread_z']}")
