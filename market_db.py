import sqlite3
import pandas as pd
from datetime import datetime
import logging

class MarketDB:
    def __init__(self, db_path="stocks.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        """Creates a connection with row factory for dictionary-like access."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize tables if they don't exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. Metadata Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                ticker TEXT PRIMARY KEY,
                company_name TEXT,
                source TEXT,
                last_updated TIMESTAMP
            )
        ''')
        
        # 2. Prices Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                date TEXT,
                ticker TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                FOREIGN KEY(ticker) REFERENCES metadata(ticker),
                PRIMARY KEY (ticker, date)
            )
        ''')
        
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices (ticker);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON prices (date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_company ON metadata (company_name);")

        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # WRITE OPERATIONS
    # ------------------------------------------------------------------

    def upsert_metadata(self, df: pd.DataFrame, source: str):
        """Batch inserts/updates company metadata."""
        if df.empty: return
        
        data = []
        now = datetime.now().isoformat()
        
        for _, row in df.iterrows():
            data.append((row['Ticker'], row['CompanyName'], source.upper(), now))

        conn = self._get_conn()
        conn.executemany('''
            INSERT OR REPLACE INTO metadata (ticker, company_name, source, last_updated)
            VALUES (?, ?, ?, ?)
        ''', data)
        conn.commit()
        logging.info(f"✅ DB: Upserted {len(data)} tickers for {source}.")
        conn.close()

    def insert_prices(self, df: pd.DataFrame):
        """Batch inserts price history."""
        if df.empty: return
        
        data = []
        for _, row in df.iterrows():
            # Handle potential missing Volume
            vol = row['Volume'] if 'Volume' in row else 0
            
            data.append((
                row['Date'], 
                row['Ticker'], 
                row['Open'], row['High'], row['Low'], row['Close'], 
                vol
            ))

        conn = self._get_conn()
        conn.executemany('''
            INSERT OR IGNORE INTO prices (date, ticker, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', data)
        conn.commit()
        logging.info(f"✅ DB: Inserted {len(data)} price records.")
        conn.close()

    # ------------------------------------------------------------------
    # READ OPERATIONS
    # ------------------------------------------------------------------

    def get_all_tickers(self, source: str = None):
        """Returns a list of all tickers present in the metadata table."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if source:
            cursor.execute("SELECT ticker FROM metadata WHERE source = ?", (source.upper(),))
        else:
            cursor.execute("SELECT ticker FROM metadata")
            
        rows = cursor.fetchall()
        conn.close()
        return [r['ticker'] for r in rows]

    def search_ticker(self, query: str):
        """Smart Search: Exact Ticker -> Prefix -> Fuzzy Name."""
        query = query.strip().upper()
        conn = self._get_conn()
        cursor = conn.cursor()

        # 1. Exact Ticker
        cursor.execute("SELECT * FROM metadata WHERE ticker = ?", (query,))
        res = cursor.fetchone()
        if res: return dict(res)

        # 2. Ticker Prefix (e.g. RELIANCE without .NS)
        cursor.execute("SELECT * FROM metadata WHERE ticker LIKE ?", (f"{query}.%",))
        res = cursor.fetchone()
        if res: return dict(res)

        # 3. Fuzzy Name
        cursor.execute("SELECT * FROM metadata WHERE company_name LIKE ? LIMIT 1", (f"%{query}%",))
        res = cursor.fetchone()
        if res: return dict(res)
        
        conn.close()
        return None

    def get_price_history(self, ticker: str, start_date: str = None, end_date: str = None):
        """Returns DataFrame of price history for a ticker."""
        conn = self._get_conn()
        
        sql = "SELECT date, open, high, low, close, volume FROM prices WHERE ticker = ?"
        params = [ticker]
        
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
            
        sql += " ORDER BY date ASC"
        
        df = pd.read_sql(sql, conn, params=params)
        conn.close()
        return df