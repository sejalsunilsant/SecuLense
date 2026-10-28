# SecuLense · Financial Research Platform

SecuLense is an executive financial research and corporate disclosure intelligence platform built on **React 18+**, **FastAPI**, **Apache Spark (PySpark)**, and **Databricks Delta Lake**. 

Designed for investment analysts, risk officers, and quantitative researchers, SecuLense ingests authentic public corporate disclosures (SEC Form 10-K and 10-Q) and market daily prices to compute paragraph-level filing diffs, evidence-backed risk factor disclosures, multi-company peer benchmarking, financial trends, and actionable research alerts.

All technical data engineering pipelines and distributed PySpark operations execute internally across the **Medallion Lakehouse (Bronze, Silver, Gold)** architecture, providing researchers with clean, actionable financial insights without infrastructure noise.

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │          React 18+ Frontend            │
                      │  (Vite · Dark Executive Terminal UI)   │
                      └───────────────────▲────────────────────┘
                                          │  HTTP / JSON / REST
                                          ▼
                      ┌────────────────────────────────────────┐
                      │        FastAPI Python Backend          │
                      │  (Uvicorn · PBKDF2 Auth · REST APIs)   │
                      └───────────────────▲────────────────────┘
                                          │
       ┌──────────────────────────────────┴──────────────────────────────────┐
       ▼                                                                     ▼
┌────────────────────────────────────────────────────────┐         ┌──────────────────┐
│      Databricks Delta Lake / PySpark Engine            │         │ SQLite Metadata  │
│                                                        │         │  & Local Auth    │
│  ┌────────────────┐ ┌────────────────┐ ┌─────────────┐ │         │ (local_auth.db)  │
│  │  Bronze Layer  │ │  Silver Layer  │ │ Gold Tables │ │         └──────────────────┘
│  │  (Raw SEC &    │ │  (Standardized │ │ (Analytics, │ │
│  │   Market APIs) │ │   Deduplicated)│ │  Benchmarking││
│  └────────────────┘ └────────────────┘ └─────────────┘ │
└────────────────────────────────────────────────────────┘
```

### Medallion Lakehouse Architecture
1. **Bronze Layer (`data/bronze`)**:
   - `data/bronze/sec`: Raw JSON/HTML submissions and filings from the SEC EDGAR API.
   - `data/bronze/market`: Raw daily OHLCV market feeds.
2. **Silver Layer (`data/silver`)**:
   - Cleaned, schema-validated, and deduplicated tables:
     - `filings`: Standardized accession numbers, CIKs, accepted timestamps, and extracted sections (`Item 1A`, `Item 7`).
     - `prices`: Cleaned daily OHLCV series, rolling 20d/50d SMAs, and daily return percentages.
     - `fundamentals`: Cleaned quarterly and annual statements (Revenue, Net Income, Margins, EPS).
3. **Gold Layer (`data/gold`)**:
   - High-performance analytical Parquet/Delta tables:
     - `companies.parquet`: Master profiles for market leaders (AAPL, MSFT, NVDA, AMZN, GOOGL, TSLA).
     - `filings.parquet`: Verified SEC 10-K/10-Q filings with direct links to official SEC EDGAR URLs.
     - `filing_diffs.parquet`: Paragraph sequence diffs tracking additions, deletions, and modifications.
     - `risk_scores.parquet`: Evidence-backed linguistic risk analysis with verbatim SEC text excerpts.
     - `daily_prices.parquet`: Historical OHLCV series with volume and technical indicators.
     - `fundamentals.parquet`: Quarterly and annual financial trajectories.
     - `company_comparisons.parquet`: Multi-company side-by-side peer benchmarking matrix.
     - `watchlist_alerts.parquet`: Actionable research alerts (e.g. Antitrust scrutiny, AI export controls).
     - `event_returns.parquet`: Event study measuring 1d, 5d, 30d, 60d, and 90d post-filing returns.
     - `data_freshness.json`: Audit trail of sources, timestamps, and layer verification.

---

## Analytical Workspaces

The platform provides 10 purpose-built research workspaces:

| Workspace | Purpose |
| :--- | :--- |
| **Overview** | Executive market pulse, portfolio KPI cards, high-priority actionable alerts, recent SEC filings, and one-click CSV export. |
| **Company Explorer** | Company metadata, historical quarterly/annual financial trends (Revenue, Net Income, Margins, EPS), verified SEC filings, and interactive price charts. |
| **Filing Comparisons** | Deep paragraph-level diff comparison engine between consecutive 10-K/10-Q filings with color-coded additions, modifications, and deletions. |
| **Risk Analysis** | Evidence-backed risk factors categorized into Regulatory, Cyber/AI, Supply Chain, and Geopolitics, accompanied by verbatim quoted excerpts. |
| **Company Comparisons** | Interactive multi-company peer benchmarking matrix comparing Revenue, Margins, Valuation (P/E), Free Cash Flow, and Risk Severity. |
| **Watchlist & Alerts** | Active watchlist management and material alerts feed with trigger diagnostics, impact horizons, and research recommendations. |
| **Market Analysis** | Technical analysis terminal with interactive OHLCV candlestick chart, volume histogram, 20-day / 50-day SMAs. |
| **Price & Returns** | Empirical event-study analysis quantifying price impact and maximum drawdowns across 1d, 5d, 30d, 60d, and 90d horizons following SEC filings. |
| **Data Provenance** | Databricks Delta Lake Medallion architecture audit dashboard, data freshness indicators, source verification, and raw CSV downloads. |
| **Ask Secu** | Deterministic financial research assistant citing exact SEC filings, financial margins, and risk disclosures. |

---

## Quick Start

### 1. Prerequisites
- Python 3.10+ (3.11 or 3.12 recommended)
- Node.js 18+

### 2. Installation & Setup

```powershell
# 1. Activate Python virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Ingest Medallion Lakehouse tables (Bronze -> Silver -> Gold)
python -m secu_lense.cli demo

# 3. Build React frontend production assets
npm --prefix frontend run build
```

---

## Running the Platform

### Standalone / Production Mode (Single Port: http://127.0.0.1:8000)
Serves both the FastAPI backend and compiled React single-page application:

```powershell
python run.py
```

### Development Mode (Hot Reload)
Starts the FastAPI API on `http://127.0.0.1:8000` and Vite dev server on `http://127.0.0.1:5173`:

```powershell
python run.py --dev
```

---

## Testing & Quality Assurance

Run the comprehensive unit test suite:

```powershell
python -m unittest discover tests
```

Tests verify:
1. `tests/test_lakehouse.py`: Medallion architecture execution, master data integrity, event returns calculation, and peer comparisons.
2. `tests/test_api.py`: FastAPI endpoints for health, auth, datasets, fundamentals, comparisons, alerts, freshness, and copilot queries.
3. `tests/test_local_auth.py`: PBKDF2 hashing (310,000 rounds), session tokens, and access control.
4. `tests/test_dataset_loader.py`: Temporal event return joins and dataset bundle validation.
5. `tests/test_pipeline.py`: Section extraction, paragraph sequence diffing, and risk scoring.
