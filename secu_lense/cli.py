"""CLI interface for SecuLense financial research platform."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .copilot import GLOSSARY
from .lakehouse import get_lakehouse_engine
from .ml_pipeline import run_training_workflow, train_spark_mllib
from .filings import compare_paragraphs, fetch_filings, get_ticker_cik
from .sources import fetch_yfinance, write_table
from .storage import initialize

log = logging.getLogger("secu_lense")


def demo():
    """Build the Databricks Delta Lake Medallion layers with real corporate SEC filings & market data."""
    config.ensure_dirs()
    initialize(config.DATA_DIR / "seculense.sqlite")
    engine = get_lakehouse_engine()
    res = engine.run_medallion_pipeline()

    # Also trigger React dashboard export
    root = Path(__file__).resolve().parents[1]
    export_script = root / "scripts" / "export_react_dashboard.py"
    if export_script.exists():
        import subprocess, sys
        subprocess.run([sys.executable, str(export_script)], cwd=root, check=False)

    print(f"Successfully generated Medallion Lakehouse tables (Bronze -> Silver -> Gold) in {res.get('duration_ms', 0)}ms")


def main():
    p = argparse.ArgumentParser(prog="python -m secu_lense.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("demo")
    sub.add_parser("lakehouse")

    b = sub.add_parser("import-demo")
    b.add_argument("--source", required=True)
    b.add_argument("--backend", choices=["pandas", "pyspark"], default="pandas")

    f = sub.add_parser("ingest-filings")
    f.add_argument("--tickers", nargs="+", required=True)
    f.add_argument("--start", default=str(date.today() - timedelta(days=730)))
    f.add_argument("--end", default=str(date.today()))

    m = sub.add_parser("ingest-prices")
    m.add_argument("--tickers", nargs="+", required=True)
    m.add_argument("--start", default="2020-01-01")
    m.add_argument("--end", default=str(date.today()))

    sub.add_parser("process")
    sub.add_parser("train")
    sub.add_parser("evaluate")
    sub.add_parser("spark-train")
    sub.add_parser("rag-build")

    a = p.parse_args()
    config.ensure_dirs()

    if a.cmd == "init":
        initialize(config.DATA_DIR / "seculense.sqlite")
        print("Initialized SecuLense storage")
    elif a.cmd in ("demo", "lakehouse"):
        demo()
    elif a.cmd == "import-demo":
        from .dataset_loader import load_demo_bundle
        result = load_demo_bundle(a.source, config.DATA_DIR / "gold", backend=a.backend)
        counts = {name: summary["rows"] for name, summary in result["validation"]["tables"].items()}
        print(f"Imported bundle via {a.backend}: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
    elif a.cmd == "ingest-filings":
        rows = []
        for t in a.tickers:
            try:
                rows += fetch_filings(t, get_ticker_cik(t, user_agent=config.SEC_USER_AGENT), a.start, a.end, config.SEC_USER_AGENT, config.DATA_DIR / "bronze/sec")
            except Exception as e:
                log.exception("Filing ingestion failed for %s: %s", t, e)
        if rows:
            write_table(pd.DataFrame(rows), config.DATA_DIR / "silver/filings/filings.parquet")
        print(f"Ingested {len(rows)} SEC filings")
    elif a.cmd == "ingest-prices":
        df = fetch_yfinance(a.tickers, a.start, a.end)
        if not df.empty:
            write_table(df, config.DATA_DIR / "silver/prices/daily_prices.parquet")
        print(f"Retrieved {len(df)} market observations; source tagged yfinance")
    elif a.cmd == "process":
        engine = get_lakehouse_engine()
        engine.run_medallion_pipeline()
        print("PySpark Medallion transforms executed.")
    elif a.cmd == "train":
        from .eda import explore
        explore(config.DATA_DIR / "gold", "artifacts/eda")
        ds, _, metrics, _ = run_training_workflow(config.DATA_DIR / "gold", "artifacts", config.DATA_DIR / "processed/ml_training_dataset.parquet", config.NEGATIVE_RETURN_THRESHOLD)
        print(f"Trained/evaluated with chronological holdout on {len(ds)} filing events")
    elif a.cmd == "evaluate":
        path = config.DATA_DIR.parent / "artifacts/evaluation/metrics.json"
        if path.exists():
            print(path.read_text(encoding="utf-8"))
        else:
            print("No evaluation found. Run `python -m secu_lense.cli train` first.")
    elif a.cmd == "spark-train":
        print(train_spark_mllib(config.DATA_DIR / "processed/ml_training_dataset.parquet", "artifacts/models/spark"))
    elif a.cmd == "rag-build":
        print("Deterministic glossary and local filing retrieval are available without building a vector index.")


if __name__ == "__main__":
    main()
