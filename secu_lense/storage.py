"""Local analytical tables and indexed SQLite application metadata."""
import sqlite3
from pathlib import Path
from contextlib import closing

SCHEMA="""
CREATE TABLE IF NOT EXISTS filings(ticker TEXT, cik TEXT, accession_number TEXT PRIMARY KEY, filing_type TEXT, filing_date TEXT, accepted_timestamp TEXT, fiscal_period_end TEXT, filing_url TEXT, raw_document_path TEXT, extraction_status TEXT);
CREATE INDEX IF NOT EXISTS idx_filings_ticker_date ON filings(ticker, filing_date);
CREATE TABLE IF NOT EXISTS model_predictions(ticker TEXT, accession_number TEXT, prediction_timestamp TEXT, prediction_horizon INTEGER, predicted_probability REAL, model_version TEXT, feature_snapshot_timestamp TEXT);
"""
def initialize(path:Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.executescript(SCHEMA)
        db.commit()
