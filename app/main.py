import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import (
    get_dashboard_data,
    get_distinct_dates_count,
    get_historical_table_data,
    get_latest_sync_timestamp,
    init_db,
    upsert_rates,
)
from app.scraper import (
    backfill_state,
    check_and_backfill,
    scrape_single_date,
)

logger = logging.getLogger("cbr_main")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

scheduler = AsyncIOScheduler()


async def scheduled_daily_sync():
    """Scheduled task executed daily at 18:15 Moscow time to fetch newest official CBR rates."""
    logger.info("Executing scheduled CBR daily rate synchronization...")
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        await scrape_single_date(client, None)
    logger.info("Scheduled daily sync completed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager:
      1. Initializes database schema and auto-seeds if fresh disk.
      2. If completely empty, quickly scrapes latest rates for instant availability.
      3. Launches 30-day historical backfill if distinct dates < 25.
      4. Schedules daily cron job at 18:15 Moscow time.
    """
    logger.info("Starting up CBR Currency Tracker application...")
    init_db()

    # Pre-fetch latest rates if database is clean to immediately populate hero cards
    if get_distinct_dates_count() == 0:
        logger.info("Initial run detected. Scraping latest rates immediately for warm start...")
        try:
            async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
                await scrape_single_date(client, None)
        except Exception as e:
            logger.warning(f"Initial warm start scrape encountered: {e}")

    # Launch historical backfill task in background so server starts responding immediately
    asyncio.create_task(check_and_backfill())

    # Configure APScheduler for 18:15 (6:15 PM) Moscow Time (Europe/Moscow)
    scheduler.add_job(
        scheduled_daily_sync,
        CronTrigger(hour=18, minute=15, timezone="Europe/Moscow"),
        id="cbr_daily_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler initialized: Scheduled run daily at 18:15 (6:15 PM) Moscow Time (Europe/Moscow).")

    yield

    logger.info("Shutting down CBR Currency Tracker application...")
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="CBR Live Currency Terminal",
    description="Institutional-grade tracker for CBR daily foreign exchange rates against RUB (USD, EUR, AED).",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for open internal communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Renders the main institutional dark mode dashboard."""
    real_today = date.today().strftime("%Y-%m-%d")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"real_today": real_today}
    )


@app.get("/api/dashboard-data")
async def get_dashboard_metrics(
    days: Optional[str] = Query(default="30", description="Timeframe in days (e.g. 7, 30, or 'all')")
):
    """
    Returns aggregated metrics and chronological historical data for USD, EUR, and AED.
    """
    parsed_days: Optional[int] = 30
    if days is not None:
        if days.lower() in ("all", "0", "-1"):
            parsed_days = None
        else:
            try:
                parsed_days = int(days)
            except ValueError:
                parsed_days = 30

    data = get_dashboard_data(parsed_days)
    data["backfill_status"] = backfill_state
    data["real_today"] = date.today().strftime("%Y-%m-%d")
    return JSONResponse(content=data)


@app.post("/api/fetch-now")
async def trigger_fetch_now():
    """
    Manually triggers an immediate scrape of the freshest published rates from CBR,
    upserts them into SQLite, and returns the updated dashboard payload.
    """
    logger.info("Manual sync requested via POST /api/fetch-now")
    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            records = await scrape_single_date(client, None)

        # Return updated dashboard data
        data = get_dashboard_data(days=30)
        data["sync_result"] = {
            "success": True,
            "records_updated": len(records),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return JSONResponse(content=data)
    except Exception as exc:
        logger.error(f"Manual sync failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape CBR rates: {str(exc)}")


@app.get("/api/history-table")
async def get_history_table(limit: int = Query(default=100, ge=1, le=1000)):
    """
    Returns tabular historical rates (Date, USD, EUR, AED) suitable for data tables and exports.
    """
    rows = get_historical_table_data(limit=limit)
    return JSONResponse(content={"records": rows, "count": len(rows)})


@app.get("/api/export-csv")
async def export_csv(days: Optional[str] = Query(default="all")):
    """
    Exports CSV formatted exchange rate records filtered by timeframe:
    7 (past week), 15 (past 15 days), 30 (past 30 days), or all (full historical dataset).
    """
    limit: Optional[int] = None
    timeframe_label = "all"
    if days and days.lower() not in ("all", "0", "-1"):
        try:
            limit = int(days)
            timeframe_label = f"{limit}d"
        except ValueError:
            limit = None
            timeframe_label = "all"

    records = get_historical_table_data(limit=limit)

    import csv
    import io
    from fastapi.responses import Response

    output = io.StringIO()
    # Write UTF-8 BOM so spreadsheet apps (Excel, Numbers) open without encoding errors
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["Date", "USD_RUB", "EUR_RUB", "AED_RUB"])
    for r in records:
        writer.writerow([
            r.get("date", ""),
            r.get("USD", ""),
            r.get("EUR", ""),
            r.get("AED", "")
        ])

    csv_data = output.getvalue()
    today_str = date.today().strftime("%Y%m%d")
    filename = f"cbr_rates_{timeframe_label}_{today_str}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint for Docker / container orchestration."""
    return {
        "status": "healthy",
        "distinct_dates": get_distinct_dates_count(),
        "last_synced": get_latest_sync_timestamp(),
        "backfill_running": backfill_state["is_running"],
    }
