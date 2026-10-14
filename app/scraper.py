import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from app.database import (
    get_distinct_dates_count,
    upsert_rates,
)

logger = logging.getLogger("cbr_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

BASE_URL = "https://www.cbr.ru/eng/currency_base/daily/"
HISTORICAL_URL = "https://www.cbr.ru/eng/currency_base/daily/?UniDbQuery.Posted=True&UniDbQuery.To={date_str}"

TARGET_CURRENCIES = {
    "USD": {"num_code": "840", "name": "US Dollar"},
    "EUR": {"num_code": "978", "name": "Euro"},
    "AED": {"num_code": "784", "name": "UAE Dirham"},
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

# In-memory backfill status for monitoring and UI feedback
backfill_state: Dict[str, Any] = {
    "is_running": False,
    "total_days": 30,
    "completed_days": 0,
    "current_date": None,
    "status": "idle",
    "last_error": None,
}


def parse_cbr_html(html_content: str, requested_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Parses the CBR HTML page and extracts USD, EUR, AED rates.
    Dynamically identifies the published date from the CBR page (UniDbQuery.To input)
    to accurately handle next-day rate publications, falling back to requested_date if needed.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_="data")
    if not table:
        logger.warning("No <table class='data'> found on CBR page.")
        return []

    # Detect the actual date published on the page
    actual_date_str: Optional[str] = None
    date_input = soup.find("input", {"name": "UniDbQuery.To"})
    if date_input and date_input.get("value"):
        val = date_input["value"].strip()
        try:
            actual_date_str = datetime.strptime(val, "%d.%m.%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    if not actual_date_str and requested_date:
        actual_date_str = requested_date.strftime("%Y-%m-%d")

    if not actual_date_str:
        actual_date_str = date.today().strftime("%Y-%m-%d")

    date_str = actual_date_str
    now_iso = datetime.now(timezone.utc).isoformat()
    scraped_records: List[Dict[str, Any]] = []

    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        num_code = cols[0].text.strip()
        char_code = cols[1].text.strip().upper()
        unit_text = cols[2].text.strip()
        currency_name = cols[3].text.strip()
        rate_text = cols[4].text.strip().replace(",", ".")

        if char_code in TARGET_CURRENCIES:
            try:
                unit = float(unit_text)
                raw_rate = float(rate_text)
                final_rate = round(raw_rate / unit, 4)

                scraped_records.append({
                    "date": date_str,
                    "currency": char_code,
                    "rate": final_rate,
                    "updated_at": now_iso,
                })
            except (ValueError, ZeroDivisionError) as err:
                logger.error(f"Error parsing rate row for {char_code} on {date_str}: {err}")

    return scraped_records


async def scrape_single_date(
    client: httpx.AsyncClient, target_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Scrapes CBR for a specific date or fetches the latest available rate if target_date is None.
    When target_date is None, fetches BASE_URL to obtain the freshest official rate.
    """
    if target_date is None:
        url = BASE_URL
        date_label = "latest"
    else:
        date_formatted = target_date.strftime("%d.%m.%Y")
        url = HISTORICAL_URL.format(date_str=date_formatted)
        date_label = date_formatted

    logger.info(f"Fetching CBR rates ({date_label}) from {url}")
    try:
        response = await client.get(url, headers=HEADERS)
        response.raise_for_status()
        records = parse_cbr_html(response.text, target_date)
        if records:
            upsert_rates(records)
            resolved_date = records[0]["date"] if records else date_label
            logger.info(f"Successfully scraped & upserted {len(records)} rates for date {resolved_date}")
        return records
    except Exception as exc:
        logger.error(f"Failed to fetch CBR rates for {date_label}: {exc}")
        return []


async def run_30_day_backfill() -> int:
    """
    Loops through the last 30 calendar days (today - 29 days up to today),
    scrapes USD, EUR, and AED, and saves them into SQLite.
    Includes a 0.2s pause between requests to respect CBR servers.
    """
    global backfill_state
    if backfill_state["is_running"]:
        logger.info("Backfill is already running. Skipping duplicate invocation.")
        return 0

    backfill_state["is_running"] = True
    backfill_state["status"] = "in_progress"
    backfill_state["completed_days"] = 0
    backfill_state["total_days"] = 30
    backfill_state["last_error"] = None

    today = date.today()
    total_saved = 0

    logger.info("=== Starting 30-day CBR historical backfill ===")

    # Use verify=False to prevent SSL errors with Russian CA certs
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        for offset in range(29, -1, -1):
            target_date = today - timedelta(days=offset)
            date_cbr_str = target_date.strftime("%d.%m.%Y")
            backfill_state["current_date"] = target_date.strftime("%Y-%m-%d")

            try:
                records = await scrape_single_date(client, target_date)
                total_saved += len(records)
            except Exception as e:
                logger.error(f"Backfill error on {date_cbr_str}: {e}")
                backfill_state["last_error"] = str(e)

            backfill_state["completed_days"] += 1
            # Rate-limiting compliance: short pause between requests
            await asyncio.sleep(0.2)

    backfill_state["is_running"] = False
    backfill_state["status"] = "completed"
    logger.info(f"=== 30-day historical backfill completed. Total records saved: {total_saved} ===")
    return total_saved


async def check_and_backfill() -> None:
    """
    Startup check: If fewer than 25 distinct dates exist in SQLite,
    automatically triggers the 30-day historical backfill.
    """
    distinct_dates = get_distinct_dates_count()
    logger.info(f"Database currently holds {distinct_dates} distinct date records.")
    if distinct_dates < 25:
        logger.warning(
            f"Fewer than 25 dates found ({distinct_dates}/25). Initiating 30-day historical backfill..."
        )
        await run_30_day_backfill()
    else:
        logger.info("Sufficient historical data present (>= 25 days). Startup backfill skipped.")
