#!/usr/bin/env python3
"""
CFTC COT Data Fetcher v3 - Exact contract name matching
"""
import os, sys, csv, json, zipfile, io, argparse
from datetime import datetime

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests --break-system-packages -q")
    import requests

try:
    import yfinance as yf
except ImportError:
    os.system(f"{sys.executable} -m pip install yfinance --break-system-packages -q")
    import yfinance as yf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
CFTC_BASE_URL = "https://www.cftc.gov/files/dea/history"

# EXACT full market names - no fuzzy matching
CONTRACT_EXACT_NAMES = {
    "BITCOIN - CHICAGO MERCANTILE EXCHANGE": "BTC",
    "ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE": "ETH",
    "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE": "SP500",
    "S&P 500 Consolidated - CHICAGO MERCANTILE EXCHANGE": "SP500",
    "S&P 500 STOCK INDEX (COMBINED) - CHICAGO MERCANTILE EXCHANGE": "SP500",
    "NASDAQ-100 Consolidated - CHICAGO MERCANTILE EXCHANGE": "NASDAQ",
    "NASDAQ-100 - CHICAGO MERCANTILE EXCHANGE": "NASDAQ",
    "E-MINI NASDAQ-100 - CHICAGO MERCANTILE EXCHANGE": "NASDAQ",
    "NASDAQ-100 STOCK INDEX (COMBINED) - CHICAGO MERCANTILE EXCHANGE": "NASDAQ",
    "RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE": "RUSSELL",
    "E-MINI RUSSELL 2000 - CHICAGO MERCANTILE EXCHANGE": "RUSSELL",
    "RUSSELL 2000 MINI - CHICAGO MERCANTILE EXCHANGE": "RUSSELL",
    "USD INDEX - ICE FUTURES U.S.": "DXY",
    "U.S. DOLLAR INDEX - ICE FUTURES U.S.": "DXY",
    "GOLD - COMMODITY EXCHANGE INC.": "GOLD",
    "SILVER - COMMODITY EXCHANGE INC.": "SILVER",
    "COPPER- #1 - COMMODITY EXCHANGE INC.": "COPPER",
    "COPPER-GRADE #1 - COMMODITY EXCHANGE INC.": "COPPER",
    "COPPER - COMMODITY EXCHANGE INC.": "COPPER",
    "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE": "OIL",
    "CRUDE OIL,LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE": "OIL",
    "WTI FINANCIAL CRUDE OIL - NEW YORK MERCANTILE EXCHANGE": "OIL",
}

PRICE_TICKERS = {
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SP500": "^GSPC",
    "NASDAQ": "^IXIC", "RUSSELL": "^RUT", "DXY": "DX-Y.NYB",
    "GOLD": "GC=F", "SILVER": "SI=F", "COPPER": "HG=F", "OIL": "CL=F",
}

ASSET_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SP500": "S&P 500",
    "NASDAQ": "Nasdaq 100", "RUSSELL": "Russell 2000", "DXY": "US Dollar Index",
    "GOLD": "Gold", "SILVER": "Silver", "COPPER": "Copper", "OIL": "Crude Oil WTI",
}

ALL_KEYS = ["BTC","ETH","SP500","NASDAQ","RUSSELL","DXY","GOLD","SILVER","COPPER","OIL"]
Z_WINDOW = 156
Z_THRESHOLD = 1.8
PCT_HIGH = 90
PCT_LOW = 10

# Build case-insensitive lookup
_LOOKUP = {k.upper().strip(): v for k, v in CONTRACT_EXACT_NAMES.items()}


def match_contract(market_name):
    return _LOOKUP.get(market_name.upper().strip())


def find_column(headers, candidates):
    h_map = {}
    for h in headers:
        key = h.upper().strip().replace(" ","_").replace("-","_").replace("(","").replace(")","")
        h_map[key] = h
    for c in candidates:
        ck = c.upper().strip().replace(" ","_").replace("-","_").replace("(","").replace(")","")
        if ck in h_map:
            return h_map[ck]
        for hk, ho in h_map.items():
            if ck in hk or hk in ck:
                return ho
    return None

COL_MARKET = ["Market_and_Exchange_Names", "Market and Exchange Names"]
COL_DATE_ISO = ["Report_Date_as_YYYY-MM-DD", "Report Date as YYYY-MM-DD"]
COL_DATE_YMD = ["As_of_Date_In_Form_YYMMDD", "As of Date in Form YYMMDD"]
COL_OI = ["Open_Interest_All", "Open Interest (All)"]
COL_NL = ["NonComm_Positions_Long_All", "Noncommercial Positions-Long (All)"]
COL_NS = ["NonComm_Positions_Short_All", "Noncommercial Positions-Short (All)"]
COL_CL = ["Comm_Positions_Long_All", "Commercial Positions-Long (All)"]
COL_CS = ["Comm_Positions_Short_All", "Commercial Positions-Short (All)"]


def download_cftc_year(year):
    url = f"{CFTC_BASE_URL}/deacot{year}.zip"
    print(f"  Downloading {year}...", end=" ", flush=True)
    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}")
            return [], []
        z = zipfile.ZipFile(io.BytesIO(resp.content))
        csv_name = z.namelist()[0]
        data = z.read(csv_name).decode('utf-8', errors='replace')
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        headers = list(rows[0].keys()) if rows else []
        print(f"{len(rows)} rows")
        return rows, headers
    except Exception as e:
        print(f"Error: {e}")
        return [], []


def debug_cftc(year=None):
    if year is None:
        year = datetime.now().year
    rows, headers = download_cftc_year(year)
    if not rows:
        return
    
    print(f"\n{'='*60}")
    sample = list(rows[0].keys())
    cm = find_column(sample, COL_MARKET)
    cd = find_column(sample, COL_DATE_ISO) or find_column(sample, COL_DATE_YMD)
    co = find_column(sample, COL_OI)
    print(f"DETECTED: market='{cm}' date='{cd}' oi='{co}'")
    
    if cm:
        names = sorted(set(r.get(cm, '') for r in rows))
        print(f"\nMARKET NAMES ({len(names)}):")
        for n in names:
            key = match_contract(n)
            if key:
                print(f"  {n} \u2705 [{key}]")
            else:
                print(f"  {n}")
    
    # Summary
    print(f"\n{'='*60}")
    print("MATCH SUMMARY:")
    matched_keys = set()
    for n in sorted(set(r.get(cm, '') for r in rows)):
        key = match_contract(n)
        if key:
            matched_keys.add(key)
            count = sum(1 for r in rows if r.get(cm,'').strip() == n.strip())
            print(f"  \u2705 {key:8s} -> {n} ({count} rows)")
    
    for k in ALL_KEYS:
        if k not in matched_keys:
            print(f"  \u274c {k:8s} -> NOT FOUND")


def parse_cftc_rows(all_rows):
    if not all_rows:
        return {k: [] for k in ALL_KEYS}
    
    sample = list(all_rows[0].keys())
    cm = find_column(sample, COL_MARKET)
    cd1 = find_column(sample, COL_DATE_ISO)
    cd2 = find_column(sample, COL_DATE_YMD)
    co = find_column(sample, COL_OI)
    cnl = find_column(sample, COL_NL)
    cns = find_column(sample, COL_NS)
    ccl = find_column(sample, COL_CL)
    ccs = find_column(sample, COL_CS)
    
    if not cm:
        print(f"  ERROR: No market column found")
        return {k: [] for k in ALL_KEYS}
    
    results = {k: [] for k in ALL_KEYS}
    
    for row in all_rows:
        mname = row.get(cm, '').strip()
        key = match_contract(mname)
        if not key:
            continue
        
        ds = ""
        if cd1:
            ds = row.get(cd1, '').strip()
        if not ds and cd2:
            raw = row.get(cd2, '').strip()
            if len(raw) == 6:
                yy = int(raw[:2])
                yr = 2000 + yy if yy < 80 else 1900 + yy
                ds = f"{yr}-{raw[2:4]}-{raw[4:6]}"
        if not ds:
            continue
        
        def safe_int(v):
            v = str(v).strip().replace(',','')
            return int(float(v)) if v else 0
        
        try:
            results[key].append({
                "date": ds,
                "open_interest": safe_int(row.get(co, 0)),
                "noncommercial_long": safe_int(row.get(cnl, 0)),
                "noncommercial_short": safe_int(row.get(cns, 0)),
                "commercial_long": safe_int(row.get(ccl, 0)),
                "commercial_short": safe_int(row.get(ccs, 0)),
            })
        except Exception:
            continue
    
    for key in ALL_KEYS:
        results[key].sort(key=lambda x: x['date'])
        seen = set()
        unique = []
        for r in results[key]:
            if r['date'] not in seen:
                seen.add(r['date'])
                unique.append(r)
        results[key] = unique
        status = f"{len(unique)} records" if unique else "NO DATA"
        print(f"  {key:8s}: {status}")
    
    return results


def download_all_cot(start_year=2015):
    current_year = datetime.now().year
    all_rows = []
    for year in range(start_year, current_year + 1):
        rows, _ = download_cftc_year(year)
        all_rows.extend(rows)
    print(f"  Total rows: {len(all_rows)}")
    return parse_cftc_rows(all_rows)


def download_latest_cot():
    rows, _ = download_cftc_year(datetime.now().year)
    return parse_cftc_rows(rows)


def fetch_prices(start_date="2015-01-01"):
    prices = {}
    for key, ticker in PRICE_TICKERS.items():
        print(f"  {key} ({ticker})...", end=" ", flush=True)
        try:
            df = yf.download(ticker, start=start_date, interval="1wk", progress=False)
            if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)
            if len(df) > 0:
                pdata = []
                cc = df['Close']
                for idx in df.index:
                    ds = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
                    val = cc.loc[idx]
                    if hasattr(val, 'iloc'):
                        val = val.iloc[0]
                    pdata.append({"date": ds, "price": round(float(val), 2)})
                prices[key] = pdata
                print(f"{len(pdata)} prices")
            else:
                prices[key] = []
                print("no data")
        except Exception as e:
            print(f"error: {e}")
            prices[key] = []
    return prices


def merge_price_csv(prices, key, csv_path):
    if not os.path.exists(csv_path):
        return prices
    cp = {}
    with open(csv_path, 'r') as f:
        for row in csv.DictReader(f):
            cp[row['Date'].strip()] = round(float(row['Close']), 2)
    existing = {p['date'] for p in prices.get(key, [])}
    merged = list(prices.get(key, []))
    for d, p in cp.items():
        if d not in existing:
            merged.append({"date": d, "price": p})
    merged.sort(key=lambda x: x['date'])
    prices[key] = merged
    print(f"  Merged {key}: {len(merged)} prices")
    return prices


def calculate_signals(cot_data):
    results = []
    for i, row in enumerate(cot_data):
        cn = row["commercial_long"] - row["commercial_short"]
        nn = row["noncommercial_long"] - row["noncommercial_short"]
        sp = cn - nn
        oi = row["open_interest"]
        nlp = (row["noncommercial_long"] / oi * 100) if oi > 0 else 0
        ws = max(0, i - Z_WINDOW + 1)
        
        nets = [cot_data[j]["commercial_long"] - cot_data[j]["commercial_short"] for j in range(ws, i+1)]
        z = 0
        if len(nets) >= 20:
            mn = sum(nets)/len(nets)
            sn = (sum((x-mn)**2 for x in nets)/len(nets))**0.5
            z = round((cn-mn)/sn, 2) if sn > 0 else 0
        
        pcts = []
        for j in range(ws, i+1):
            oj = cot_data[j]["open_interest"]
            if oj > 0:
                pcts.append(cot_data[j]["noncommercial_long"]/oj*100)
        pctile = 50
        if len(pcts) >= 20:
            rk = sum(1 for x in pcts if x <= nlp)
            pctile = round(rk/len(pcts)*100, 1)
        
        sps = [(cot_data[j]["commercial_long"]-cot_data[j]["commercial_short"])-(cot_data[j]["noncommercial_long"]-cot_data[j]["noncommercial_short"]) for j in range(ws, i+1)]
        sz = 0
        if len(sps) >= 20:
            ms = sum(sps)/len(sps)
            ss = (sum((x-ms)**2 for x in sps)/len(sps))**0.5
            sz = round((sp-ms)/ss, 2) if ss > 0 else 0
        
        results.append({
            "date": row["date"], "commercial_net": cn, "noncommercial_net": nn,
            "noncomm_long_pct_oi": round(nlp, 2), "spread": sp,
            "z_score": z, "percentile": pctile, "spread_z": sz,
            "z_signal": "bullish" if z > Z_THRESHOLD else ("bearish" if z < -Z_THRESHOLD else None),
            "pct_signal": "bearish" if pctile > PCT_HIGH else ("bullish" if pctile < PCT_LOW else None),
            "spread_signal": "bullish" if sz > Z_THRESHOLD else ("bearish" if sz < -Z_THRESHOLD else None),
        })
    return results


def build_signal_history(pl, signals):
    hist = []
    for i, s in enumerate(signals):
        for st, sk in [("z_score","z_signal"),("pct_oi","pct_signal"),("spread","spread_signal")]:
            if s[sk] and i < len(pl) and pl[i] > 0:
                e = {"date":s["date"],"type":st,"direction":s[sk],"price_at_signal":pl[i],
                     "z_score":s["z_score"],"percentile":s["percentile"],"spread_z":s["spread_z"],"returns":{}}
                for w in [4,8,13,26]:
                    fi = i + w
                    if fi < len(pl) and pl[i] > 0:
                        e["returns"][f"{w}w"] = round((pl[fi]-pl[i])/pl[i]*100, 2)
                    else:
                        e["returns"][f"{w}w"] = None
                hist.append(e)
    return hist


def build_dashboard_data(cot_all, prices_all):
    result = {}
    for key in ALL_KEYS:
        cot = cot_all.get(key, [])
        pd_list = prices_all.get(key, [])
        if not cot:
            print(f"  {key}: No COT data, skipping")
            continue
        
        pm = {p["date"]: p["price"] for p in pd_list}
        pds = sorted(pm.keys())
        
        ap = []
        for c in cot:
            cd = c["date"]
            if cd in pm:
                ap.append(pm[cd])
            else:
                best, bd = 0, 999
                try:
                    cdt = datetime.strptime(cd, "%Y-%m-%d")
                    for p in pds:
                        d = abs((datetime.strptime(p, "%Y-%m-%d") - cdt).days)
                        if d < bd:
                            bd = d
                            best = pm[p]
                except:
                    pass
                ap.append(best)
        
        for i in range(len(ap)):
            if ap[i] == 0 and i > 0:
                ap[i] = ap[i-1]
        
        sigs = calculate_signals(cot)
        sh = build_signal_history(ap, sigs)
        
        wd = []
        for i in range(len(cot)):
            wd.append({
                "date": cot[i]["date"],
                "price": round(ap[i], 2) if i < len(ap) else 0,
                "open_interest": cot[i]["open_interest"],
                "commercial_long": cot[i]["commercial_long"],
                "commercial_short": cot[i]["commercial_short"],
                "noncommercial_long": cot[i]["noncommercial_long"],
                "noncommercial_short": cot[i]["noncommercial_short"],
                **sigs[i],
            })
        
        result[key] = {
            "name": ASSET_NAMES[key], "ticker": PRICE_TICKERS[key],
            "cot_code": key, "data": wd, "signal_history": sh,
        }
        lt = wd[-1] if wd else {}
        print(f"  {key}: {len(wd)} weeks, z={lt.get('z_score','-')}, pct={lt.get('percentile','-')}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--initial', action='store_true')
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--debug-year', type=int, default=None)
    parser.add_argument('--start-year', type=int, default=2015)
    parser.add_argument('--btc-csv', type=str, default=None)
    parser.add_argument('--eth-csv', type=str, default=None)
    args = parser.parse_args()
    
    if args.debug:
        debug_cftc(args.debug_year)
        return
    
    if not args.initial and not args.update:
        print("Usage: --initial | --update | --debug")
        sys.exit(1)
    
    os.makedirs(DATA_DIR, exist_ok=True)
    out = os.path.join(DATA_DIR, "cot_dashboard_data.json")
    
    if args.initial:
        print(f"=== INITIAL: {args.start_year}-{datetime.now().year} ===")
        cot_all = download_all_cot(args.start_year)
    else:
        if os.path.exists(out):
            with open(out) as f:
                existing = json.load(f)
            latest = download_latest_cot()
            cot_all = {}
            for key in ALL_KEYS:
                ec, ed = [], set()
                if key in existing:
                    for r in existing[key].get("data", []):
                        ed.add(r["date"])
                        ec.append({k: r[k] for k in ["date","open_interest","commercial_long","commercial_short","noncommercial_long","noncommercial_short"]})
                nc = 0
                for r in latest.get(key, []):
                    if r["date"] not in ed:
                        ec.append(r)
                        nc += 1
                ec.sort(key=lambda x: x["date"])
                cot_all[key] = ec
                if nc:
                    print(f"  {key}: +{nc} new")
        else:
            print("No existing data. Running --initial...")
            cot_all = download_all_cot()
    
    total = sum(len(v) for v in cot_all.values())
    if total == 0:
        print("\n*** No COT data matched! Run --debug to check names:")
        print("  python fetch_cot_real.py --debug")
        sys.exit(1)
    
    print(f"\n=== Fetching prices ===")
    start = f"{args.start_year}-01-01" if args.initial else f"{datetime.now().year}-01-01"
    prices = fetch_prices(start)
    if args.btc_csv:
        prices = merge_price_csv(prices, "BTC", args.btc_csv)
    if args.eth_csv:
        prices = merge_price_csv(prices, "ETH", args.eth_csv)
    
    print(f"\n=== Building dashboard ===")
    data = build_dashboard_data(cot_all, prices)
    
    with open(out, 'w') as f:
        json.dump(data, f)
    
    mb = os.path.getsize(out)/1024/1024
    print(f"\n\u2705 Saved: {out} ({mb:.1f} MB)")
    print(f"Assets: {list(data.keys())}")

if __name__ == "__main__":
    main()
