# retriever.py
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone
import time
import os
import io
import logging
from typing import List, Union, Optional

from market_db import MarketDB 

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------

# Ensure data directory exists
os.makedirs("data", exist_ok=True)
db = MarketDB(os.path.join("data", "stocks.db"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# -----------------------------------------------------------------------------
# CORE LOGIC: THE UNIVERSAL SYNCER (NEW)
# -----------------------------------------------------------------------------

def sync_ticker_data(
    tickers: Union[str, List[str]], 
    period: str = "1d", 
    start: Optional[str] = None, 
    end: Optional[str] = None
) -> str:
    """
    Universal function to Download -> Clean -> Save to DB.
    Can be called by Agent (for 1 stock) or Daily Cron (for 500 stocks).
    """
    if isinstance(tickers, str):
        tickers = [tickers]
        
    if not tickers:
        return "No tickers provided."

    logging.info(f"📥 Syncing {len(tickers)} tickers (Period: {period}, Range: {start}-{end})...")

    try:
        # 1. Download
        data = yf.download(
            tickers, 
            period=period, 
            start=start, 
            end=end, 
            group_by="ticker", 
            auto_adjust=True, 
            progress=False, 
            threads=False, # Safe mode
            timeout=20
        )
        
        if data.empty:
            return "No data found."

        # 2. Clean & Format
        # Handle the case where yfinance returns single-level columns for 1 ticker
        if len(tickers) == 1:
            # Force it to match the multi-index structure or standardise it
            df = data.reset_index()
            df["Ticker"] = tickers[0]
        else:
            df = data.stack(level=0, future_stack=True).reset_index()
            if "level_1" in df.columns: 
                df.rename(columns={"level_1": "Ticker"}, inplace=True)
            elif "Ticker" not in df.columns: 
                df["Ticker"] = tickers[0]

        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        
        # 3. Save to DB
        db.insert_prices(df)
        
        return f"Successfully synced {len(tickers)} stocks."

    except Exception as e:
        err_msg = f"Sync failed: {e}"
        logging.error(err_msg)
        return err_msg

# -----------------------------------------------------------------------------
# TOOL 1: FETCH ACTIVE LISTS (Unchanged)
# -----------------------------------------------------------------------------

def fetch_active_nse_data() -> pd.DataFrame:
    """Fetch active NSE equity tickers."""
    url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
    r = requests.get(url, headers=HEADERS, timeout=10)
    df = pd.read_csv(io.StringIO(r.text))
    
    if "SYMBOL" in df.columns:
        df = df[["SYMBOL", "NAME OF COMPANY"]].copy()
    else:
        df.columns = [c.upper() for c in df.columns]
        df = df[["SYMBOL", "NAME OF COMPANY"]].copy()
        
    df.columns = ["Ticker", "CompanyName"]
    df["Ticker"] = df["Ticker"].astype(str) + ".NS"
    return df

def fetch_active_bse_data() -> pd.DataFrame:
    """Fetch active BSE equity tickers."""
    url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Scripcode=&industry=&segment=Equity&status=Active"
    r = requests.get(url, headers=HEADERS, timeout=10)
    df = pd.DataFrame(r.json())

    col_map = {c.lower().replace("_", ""): c for c in df.columns}
    id_key = next((k for k in col_map if k in ["scripcode", "scripcd", "code"]), None)
    name_key = next((k for k in col_map if k in ["scripname", "name", "companyname"]), None)

    real_id_col, real_name_col = col_map[id_key], col_map[name_key]
    df = df[[real_id_col, real_name_col]].copy()
    df.columns = ["Ticker", "CompanyName"]
    df["Ticker"] = df["Ticker"].astype(str) + ".BO"
    return df

# -----------------------------------------------------------------------------
# TOOL 2: FETCH DAILY PRICES (Refactored to use Sync)
# -----------------------------------------------------------------------------

def fetch_daily_prices(tickers: List[str], batch_size: int = 150) -> None:
    """Fetch daily OHLCV data using the new sync function."""
    if not tickers: return
    
    total = len(tickers)
    for i in range(0, total, batch_size):
        batch = tickers[i:i + batch_size]
        logging.info(f"Processing batch {i} - {i + len(batch)}")
        
        # Call the universal syncer
        sync_ticker_data(batch, period="1d")
        
        time.sleep(2) # Be polite

# -----------------------------------------------------------------------------
# ORCHESTRATOR (Unchanged)
# -----------------------------------------------------------------------------

def run_full_refresh():
    logging.info("=== NSE REFRESH ===")
    try:
        nse_df = fetch_active_nse_data()
        db.upsert_metadata(nse_df, "NSE")
        fetch_daily_prices(nse_df["Ticker"].tolist())
    except Exception as e:
        logging.error(f"NSE Failed: {e}")

    logging.info("=== BSE REFRESH ===")
    try:
        bse_df = fetch_active_bse_data()
        db.upsert_metadata(bse_df, "BSE")
        fetch_daily_prices(bse_df["Ticker"].tolist())
    except Exception as e:
        logging.error(f"BSE Failed: {e}")

if __name__ == "__main__":
    print("[+] RETRIEVER READY")
    # run_full_refresh()