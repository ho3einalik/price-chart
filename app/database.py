import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Resolve default database path: allow override via environment variable
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.getcwd(), "data", "rates.db"))


def get_db_connection() -> sqlite3.Connection:
    """Creates and returns a connection to the SQLite database with WAL mode enabled."""
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high performance concurrent reads and writes
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db() -> None:
    """Initializes the database schema if it doesn't already exist."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                date TEXT NOT NULL,
                currency TEXT NOT NULL,
                rate REAL NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (date, currency)
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rates_currency_date 
            ON exchange_rates(currency, date);
        """)
        conn.commit()


def upsert_rates(rates: List[Dict[str, Any]]) -> int:
    """
    Inserts or updates exchange rate records in the database.
    Expected dict structure: {'date': 'YYYY-MM-DD', 'currency': 'USD', 'rate': float, 'updated_at': str}
    """
    if not rates:
        return 0

    query = """
        INSERT INTO exchange_rates (date, currency, rate, updated_at) 
        VALUES (?, ?, ?, ?) 
        ON CONFLICT(date, currency) DO UPDATE SET 
            rate = excluded.rate, 
            updated_at = excluded.updated_at;
    """
    data = [
        (
            item["date"],
            item["currency"].upper(),
            float(item["rate"]),
            item.get("updated_at", datetime.now(timezone.utc).isoformat())
        )
        for item in rates
    ]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, data)
        conn.commit()
        return cursor.rowcount


def get_distinct_dates_count() -> int:
    """Returns the total number of distinct dates present in exchange_rates."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT date) FROM exchange_rates;")
        row = cursor.fetchone()
        return row[0] if row else 0


def get_latest_sync_timestamp() -> Optional[str]:
    """Returns the most recent updated_at timestamp across all records."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(updated_at) FROM exchange_rates;")
        row = cursor.fetchone()
        return row[0] if row and row[0] else None


def get_dashboard_data(days: Optional[int] = 30) -> Dict[str, Any]:
    """
    Retrieves aggregated dashboard data for USD, EUR, and AED.
    Returns:
    {
        "USD": {
            "current_rate": float,
            "current_date": str,
            "previous_rate": float,
            "change_abs": float,
            "change_pct": float,
            "high_30d": float,
            "low_30d": float,
            "history": [{"date": "YYYY-MM-DD", "rate": float}, ...]
        },
        ...
        "last_synced": str | None,
        "available_dates_count": int
    }
    """
    target_currencies = ["USD", "EUR", "AED"]
    result: Dict[str, Any] = {}

    with get_db_connection() as conn:
        cursor = conn.cursor()

        for curr in target_currencies:
            # 1. Fetch latest records up to `days` limit (or all if days is None or <= 0)
            if days and days > 0:
                cursor.execute(
                    """
                    SELECT date, rate, updated_at
                    FROM exchange_rates
                    WHERE currency = ?
                    ORDER BY date DESC
                    LIMIT ?
                    """,
                    (curr, days)
                )
            else:
                cursor.execute(
                    """
                    SELECT date, rate, updated_at
                    FROM exchange_rates
                    WHERE currency = ?
                    ORDER BY date DESC
                    """,
                    (curr,)
                )
            
            rows = cursor.fetchall()
            # Rows are in descending order (latest first). Reverse for chronological chart.
            chronological_rows = list(reversed(rows))

            if not rows:
                result[curr] = {
                    "current_rate": 0.0,
                    "current_date": "N/A",
                    "previous_rate": 0.0,
                    "change_abs": 0.0,
                    "change_pct": 0.0,
                    "high_30d": 0.0,
                    "low_30d": 0.0,
                    "history": []
                }
                continue

            latest = rows[0]
            current_rate = round(float(latest["rate"]), 4)
            current_date = str(latest["date"])

            # Determine previous day rate (row at index 1 in DESC list)
            if len(rows) > 1:
                prev = rows[1]
                previous_rate = round(float(prev["rate"]), 4)
            else:
                previous_rate = current_rate

            change_abs = round(current_rate - previous_rate, 4)
            change_pct = round((change_abs / previous_rate) * 100, 2) if previous_rate != 0 else 0.0

            # 2. Compute 30-day High and Low specifically across last 30 available records
            cursor.execute(
                """
                SELECT MAX(rate) as max_r, MIN(rate) as min_r
                FROM (
                    SELECT rate
                    FROM exchange_rates
                    WHERE currency = ?
                    ORDER BY date DESC
                    LIMIT 30
                )
                """,
                (curr,)
            )
            range_row = cursor.fetchone()
            high_30d = round(float(range_row["max_r"]), 4) if range_row and range_row["max_r"] is not None else current_rate
            low_30d = round(float(range_row["min_r"]), 4) if range_row and range_row["min_r"] is not None else current_rate

            # Build history list
            history = [
                {"date": str(r["date"]), "rate": round(float(r["rate"]), 4)}
                for r in chronological_rows
            ]

            result[curr] = {
                "current_rate": current_rate,
                "current_date": current_date,
                "previous_rate": previous_rate,
                "change_abs": change_abs,
                "change_pct": change_pct,
                "high_30d": high_30d,
                "low_30d": low_30d,
                "history": history
            }

        # Meta properties
        result["last_synced"] = get_latest_sync_timestamp()
        result["available_dates_count"] = get_distinct_dates_count()

    return result


def get_historical_table_data(limit: int = 15) -> List[Dict[str, Any]]:
    """
    Returns recent dates with USD, EUR, and AED rates formatted for a unified table.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, currency, rate
            FROM exchange_rates
            WHERE date IN (
                SELECT DISTINCT date 
                FROM exchange_rates 
                ORDER BY date DESC 
                LIMIT ?
            )
            ORDER BY date DESC, currency ASC;
            """,
            (limit,)
        )
        rows = cursor.fetchall()

    grouped: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        d = r["date"]
        if d not in grouped:
            grouped[d] = {"date": d, "USD": None, "EUR": None, "AED": None}
        grouped[d][r["currency"]] = round(float(r["rate"]), 4)

    return list(grouped.values())
