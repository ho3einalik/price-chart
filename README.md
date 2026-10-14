# 🏦 CBR Live Currency Terminal (RUB)

An institutional-grade, dark-mode financial currency tracking terminal built with **FastAPI**, **SQLite**, and **Docker**. Scrapes official foreign exchange fixing rates against the Russian Ruble (**RUB**) directly from the **Central Bank of Russia (CBR)** for **USD**, **EUR**, and **AED**, with automated historical backfills and daily scheduled updates.

---

## ⚡ Key Features

- **Jumbo Hero Price Display:** Real-time official rates rendered in high-contrast monospaced typography with Russian Ruble (`₽`) currency symbols.
- **Dynamic Delta Indicator:** Immediate visual delta compared to yesterday's rate (absolute change and percentage with emerald `▲` / crimson `▼` badges).
- **Interactive ApexCharts:** Area charts with smooth spline curves, gradient fills, auto-scaling Y-axes, and custom dark tooltips.
- **View Modes:**
  - **Focused View:** Wide interactive chart with instant currency tabs (`USD`, `EUR`, `AED`).
  - **3-Grid View:** Side-by-side comparative layout for all 3 currencies.
- **Daily Automated Cron Synchronization:** Automatically scrapes and saves fresh daily rates every day at **06:00 Moscow Time (MSK / UTC+3)** via `APScheduler`.
- **Automatic 30-Day Historical Backfill:** On initial startup, if fewer than 25 distinct dates exist, the system automatically scrapes and backfills the last 30 calendar days from CBR archives.
- **Historical Ledger & CSV Export:** Built-in collapsible ledger table showing historical rates with one-click CSV export.
- **Production Ready & Dockerized:** Runs out of the box with `docker compose up -d` on port `8050:8000`.

---

## 🏗️ Architecture & Project Structure

```text
price-chart/
├── app/
│   ├── __init__.py          # Package marker
│   ├── main.py              # FastAPI app, APScheduler lifespan, and REST endpoints
│   ├── database.py          # SQLite schema, WAL mode, upsert & analytics queries
│   ├── scraper.py           # CBR HTML parser, date binding, & 30-day backfill
│   └── templates/
│       └── index.html       # Institutional Dark Mode UI (TailwindCSS + ApexCharts)
├── data/                    # SQLite database storage (rates.db)
├── requirements.txt         # Production dependencies
├── Dockerfile               # Multi-stage Python 3.11 container with health check
├── docker-compose.yml       # Container orchestration (port 8050:8000)
└── README.md
```

---

## 🚀 Quick Start

### Option 1: Running with Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/ho3einalik/price-chart.git
cd price-chart

# Start with Docker Compose
docker compose up -d
```

Open your browser at: **[http://localhost:8050](http://localhost:8050)**

### Option 2: Running Locally with Python

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the Uvicorn server
uvicorn app.main:app --host 0.0.0.0 --port 8050 --reload
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the institutional web dashboard |
| `GET` | `/api/dashboard-data?days=30` | Returns current rates, deltas, 30D extremes, and chart time-series |
| `POST` | `/api/fetch-now` | Triggers immediate CBR live scrape and updates SQLite |
| `GET` | `/api/history-table?limit=30` | Returns tabular historical rates for ledger & CSV exports |
| `GET` | `/api/health` | Container healthcheck & database status |

---

## ⏱️ Scheduling Details

The app includes an integrated `AsyncIOScheduler` configured in FastAPI's `lifespan`:
- **Timezone:** `Europe/Moscow` (UTC+3)
- **Schedule:** Every day at **06:00 AM MSK**
- Manual triggers can be issued anytime via `POST /api/fetch-now` or through the **"Sync Now"** button on the UI.
