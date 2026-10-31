import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "market.db"

def connect():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY(symbol, date)
        )
    """)
    con.commit()
    return con

def save_prices(rows, upsert=False):
    with connect() as con:
        before = con.total_changes
        if upsert:
            con.executemany("""
                INSERT INTO prices (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open = COALESCE(prices.open, excluded.open),
                    high = CASE WHEN prices.high IS NULL THEN excluded.high ELSE MAX(excluded.high, prices.high) END,
                    low = CASE WHEN prices.low IS NULL THEN excluded.low ELSE MIN(excluded.low, prices.low) END,
                    close = excluded.close,
                    volume = excluded.volume
            """, rows)
        else:
            con.executemany("""
                INSERT OR IGNORE INTO prices
                (symbol, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, rows)
        con.commit()
        return con.total_changes - before
