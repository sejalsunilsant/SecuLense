# SecuLense

SecuLense is an educational research prototype for comparing corporate filing disclosures with historical market behavior. It does not provide investment advice. Synthetic demo prices are explicitly tagged and must not be mistaken for real performance.

## Quick start

Requires Python 3.10+ (3.11 recommended). From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m secu_lense.cli init
python -m secu_lense.cli demo
cd frontend
npm install
npm run dashboard
```

On macOS/Linux activate with `source .venv/bin/activate`. Demo data is generated in `data/gold` and will change as the current date changes. Example ticker, filing narrative, and prices are synthetic.

## Workflows

```bash
python -m secu_lense.cli demo
python -m secu_lense.cli import-demo --source "E:\\datasets seculense"
python -m secu_lense.cli ingest-filings --tickers AAPL MSFT --start 2023-01-01 --end 2025-12-31
python -m secu_lense.cli ingest-prices --tickers AAPL MSFT --start 2020-01-01 --end 2025-01-01
python -m secu_lense.cli process
python -m secu_lense.cli train
python -m secu_lense.cli evaluate
python scripts/run_ml_pipeline.py
python -m secu_lense.cli spark-train  # optional; requires pyspark
python -m secu_lense.cli rag-build
pytest
```

SEC ingestion uses the official `www.sec.gov/files/company_tickers.json`, `data.sec.gov/submissions`, and filing archive endpoints, identifies amendments and retains accession/source URL metadata. Set a descriptive `SEC_USER_AGENT` with contact information before live use. Requests have timeouts; SEC filings are cached by accession. SEC limits and market-data availability can affect coverage. Market prices use the yfinance adapter and retain the source label; yfinance is a community library and data availability/terms can change. No external network calls occur in the tests or demo.

`import-demo` loads the supplied synthetic bundle (`companies.csv`, `filings.csv`, `risk_scores.csv`, `filing_diffs.csv`, `prices/daily_prices.csv`, glossary CSV, and educational Q&A JSON) into Parquet tables in `data/gold`. Pandas is the default loader; install `.[spark]` and pass `--backend pyspark` to use Spark for source loading and Parquet writes. Event returns use the last close on/before filing date as the baseline and only later observed trading sessions for 1, 5, 30, 60, and 90-session horizons. Unsupported horizons remain null with an explicit quality status. A validation report records missing cells, duplicate rows/keys, and invalid dates. Every source row remains marked synthetic; no actual SEC or market history is represented.

For the provided folder, run:

```powershell
python -m secu_lense.cli import-demo --source ".\seculense_demo_data"
cd frontend
npm install
npm run dashboard
```

If the bundle is stored outside this repository, give `--source` its full path. The React dashboard has plain-English company, filing-change, risk-signal, market-analysis, price-move, learning, and local Ask Secu views. On first start, create the first local account with a username and password of at least 10 characters; later, use **Create an account** on the sign-in screen to add another local user. Passwords are PBKDF2-hashed and the browser receives an HttpOnly session cookie that expires after 12 hours. Accounts and sessions stay in the ignored local `data/local_auth.sqlite3` file. This built-in sign-in is for loopback/local use only; do not expose its HTTP server publicly. Ask Secu answers dataset and glossary questions using deterministic local summaries; it requires no API key. The prominent synthetic-data warning is always displayed. The earlier Streamlit UI remains available with `streamlit run app.py`.

The React **Market analysis** page can retrieve real US daily OHLCV bars from Massive. Create a local `.env` file from `.env.example`, set `MASSIVE_API_KEY` to your Massive key, then restart `npm run dashboard`. The key is only read by the loopback Python backend and is never sent to React. Responses are cached for 15 minutes. If no key is configured or the provider request fails, the chart clearly falls back to the synthetic sample. Only the market-analysis price chart switches to provider data; demo company metadata, filings, filing changes, risk scores, and filing-event returns remain synthetic and are not joined to real prices. Massive plan access, delays, and licensing depend on the account; the dashboard labels the provider source and retrieval time.

## Architecture and data

- `secu_lense/filings.py`: SEC mapping/submissions ingestion, tolerant HTML extraction, paragraph comparison.
- `analytics.py`: validated Pydantic risk records, deterministic evidence-based categories and severity, normalized risk change score, trading-day event returns.
- `sources.py`: replaceable market data adapter and Parquet/JSONL persistence.
- `spark_jobs.py`: optional partitioned PySpark de-duplication job (`pip install -e ".[spark]"`).
- `copilot.py`: local lexical retrieval, evidence excerpts, glossary and quiz. It does not fabricate unsupported responses.
- `cli.py`: init, demo, selected-ticker ingestion, processing status, model and RAG commands.
- `frontend/`: responsive React dashboard with plain-English company, filing-change, risk-signal, price-move, learning, and local Ask Secu views. `npm run dashboard` exports the local Parquet tables before starting Vite; it needs no API key.
- `scripts/export_react_dashboard.py`: exports locally loaded Parquet tables for the React app.
- `scripts/local_web_server.py`: loopback-only account setup, sign-in, session, and protected data endpoints for the React dashboard.
- `app.py`: earlier Streamlit exploration and Model Lab app (`streamlit run app.py`).
- `storage.py`: SQLite metadata and indexes. SQLite is initialized; analytical tables are Parquet where PyArrow is present (JSONL fallback otherwise).

Tables produced: `filings`, `filing_sections`, `filing_diffs`, `risk_scores`, `daily_prices`, and `event_returns`, under `data/gold`. Spark is optional. `.env.example` lists configuration for optional LLM/provider, MongoDB, vector store, and Spark settings. The present copilot uses deterministic retrieval; hosted APIs, Ollama, embeddings, MongoDB, and S3 are not wired as active backends in this MVP.

## Limitations and next steps

The local baseline uses lexical similarity and keyword risk categories; it is not an LLM risk classifier or semantic embedding model. HTML section extraction is heuristic and records missing/short extraction explicitly. SEC ingestion currently handles recent submissions returned by the SEC endpoint; historical filing archives/index crawling and incremental refresh orchestration need further work. The local ML pipeline builds filing-event features and calendar/trading-session targets, purges time splits, fits preprocessing only on training folds, and compares Dummy, Logistic Regression, Random Forest, and Gradient Boosting. The 30-event demo produces only six held-out test events per target, so artifacts are marked insufficiently evaluated and `predict_filing_risk` suppresses probabilities. These synthetic metrics are pipeline checks only. Spark has a separate optional MLlib path; PySpark is not required for the Pandas run and was not installed for this verification.

## Machine-learning pipeline

One command runs EDA, the leakage-safe event dataset build, chronological training/evaluation, and artifacts using only local Parquet data:

```powershell
python scripts/run_ml_pipeline.py
```

The individual steps are `scripts/01_explore_data.py`, `02_build_training_dataset.py`, `03_train_models.py`, `04_evaluate_models.py`, and `05_generate_predictions.py`. The CLI equivalents `python -m secu_lense.cli train` and `evaluate` are also available. If the original CSV bundle has not yet been imported, run `python -m secu_lense.cli import-demo --source "<bundle folder>"` first.

Features are filing type/sector, event-local risk/diff aggregates, and market features using the last close strictly before the filing date. Preprocessing uses training-fitted median/mode imputers, scaling, and one-hot encoding. The 1-day target is the first close strictly after filing, 5-day means five later trading sessions, and 30/60/90-day outcomes use the first observed close on or after the corresponding calendar date. Returns use adjusted close when available and close as row-level fallback. Maximum drawdown runs from the pre-filing baseline to the outcome close. The configured negative threshold defaults to -5%; it can be changed with `--threshold` on the dataset-build/unified script. Splits are chronological and purge the target horizon around boundaries. No ticker or accession identifiers enter the model features.

Outputs: cleaned filing-event features and targets at `data/processed/ml_training_dataset.parquet`, a data dictionary alongside it, EDA plots/report under `artifacts/eda/`, joblib models and metadata under `artifacts/models/`, metrics under `artifacts/evaluation/`, and confusion/model/feature-effect plots under `artifacts/plots/`. Model comparisons use validation data; test metrics are held out. Probability generation reports a status and does not return a probability unless the held-out sample has at least ten events and both classes. Feature effects are descriptive, not causal. `python -m secu_lense.cli spark-train` runs the optional Spark MLlib classifiers after installing `python -m pip install -e ".[spark]"`.

For production: build multi-year point-in-time labeled samples from real filings and appropriately licensed market data, improve date/time alignment and benchmark-relative event studies, audit extraction across issuer templates, and run repeated out-of-time validation and probability calibration. Do not infer predictive validity from this synthetic demonstration.
