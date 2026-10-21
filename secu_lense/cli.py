from __future__ import annotations
import argparse, json, logging
from datetime import date, timedelta
import numpy as np
import pandas as pd
from . import config
from .analytics import analyze_risk, trading_event
from .copilot import GLOSSARY
from .dataset_loader import load_demo_bundle
from .ml_pipeline import run_training_workflow, train_spark_mllib
from .filings import compare_paragraphs, fetch_filings, get_ticker_cik
from .sources import fetch_yfinance, write_table
from .storage import initialize

log=logging.getLogger("secu_lense")
def demo():
    config.ensure_dirs(); initialize(config.DATA_DIR/"seculense.sqlite")
    filings=[]; sections=[]; risks=[]; diffs=[]; prices=[]; events=[]
    tickers=config.WATCHLIST[:3] or ["DEMO"]
    rng=np.random.default_rng(41); dates=pd.bdate_range(end=pd.Timestamp.today().normalize(),periods=260)
    for n,ticker in enumerate(tickers):
        prev_acc=f"2023{n+1:02d}00000001"; acc=f"2024{n+1:02d}00000001"
        old="We face competition and pricing pressure in our markets. Customer demand may change."
        current="We face increased competition and pricing pressure in our markets. Our largest suppliers may experience disruptions, which could materially affect delivery schedules."
        for year,accession in ((2023,prev_acc),(2024,acc)):
            text=old if year==2023 else current; filing_date=f"{year}-02-20"
            filings.append({"ticker":ticker,"cik":"0000000000","accession_number":accession,"filing_type":"10-K","filing_date":filing_date,"accepted_timestamp":None,"fiscal_period_end":f"{year}-12-31","filing_url":None,"raw_document_path":None,"extraction_status":"synthetic"})
            sections.append({"ticker":ticker,"accession_number":accession,"section_name":"Item 1A: Risk Factors","paragraph_id":"0","paragraph_text":text,"extraction_status":"synthetic"})
            if year==2024:
                for d in compare_paragraphs(old,current):
                    diffs.append(dict(ticker=ticker,current_accession=acc,previous_accession=prev_acc,section_name="Item 1A: Risk Factors",**d))
                    if d["change_type"] in ("new","modified"): risks.append(analyze_risk(ticker,d["new_text"],d.get("old_text"),acc,filing_date).model_dump())
        close=(80+5*n)*np.cumprod(1+rng.normal(.00035,.016,len(dates)))
        rows=[{"ticker":ticker,"trade_date":dt,"open":float(c*.998),"high":float(c*1.01),"low":float(c*.99),"close":float(c),"adjusted_close":float(c),"volume":int(rng.integers(1_000_000,5_000_000)),"data_source":"synthetic_demo"} for dt,c in zip(dates,close)]
        prices.extend(rows)
        for e in trading_event(pd.DataFrame(rows),str(dates[-100].date())): events.append(dict(ticker=ticker,accession_number=acc,benchmark_return=None,relative_return=None,**e))
    tables={"filings":pd.DataFrame(filings),"filing_sections":pd.DataFrame(sections),"filing_diffs":pd.DataFrame(diffs),"risk_scores":pd.DataFrame(risks),"daily_prices":pd.DataFrame(prices),"event_returns":pd.DataFrame(events)}
    for name,df in tables.items(): write_table(df,config.DATA_DIR/"gold"/(name+".parquet"))
    (config.DATA_DIR/"gold/glossary.json").write_text(json.dumps(GLOSSARY,indent=2),encoding="utf-8")
    print(f"Generated clearly labeled synthetic demo data for {len(tickers)} companies at {config.DATA_DIR.resolve()}")

def main():
    p=argparse.ArgumentParser(prog="python -m secu_lense.cli"); sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init"); sub.add_parser("demo")
    b=sub.add_parser("import-demo"); b.add_argument("--source",required=True); b.add_argument("--backend",choices=["pandas","pyspark"],default="pandas")
    f=sub.add_parser("ingest-filings"); f.add_argument("--tickers",nargs="+",required=True); f.add_argument("--start",default=str(date.today()-timedelta(days=730))); f.add_argument("--end",default=str(date.today()))
    m=sub.add_parser("ingest-prices"); m.add_argument("--tickers",nargs="+",required=True); m.add_argument("--start",default="2020-01-01"); m.add_argument("--end",default=str(date.today()))
    sub.add_parser("process"); sub.add_parser("train"); sub.add_parser("evaluate"); sub.add_parser("spark-train"); sub.add_parser("rag-build")
    a=p.parse_args(); config.ensure_dirs()
    if a.cmd=="init": initialize(config.DATA_DIR/"seculense.sqlite"); print("Initialized SecuLense storage")
    elif a.cmd=="demo": demo()
    elif a.cmd=="import-demo":
        result=load_demo_bundle(a.source,config.DATA_DIR/"gold",backend=a.backend)
        counts={name:summary["rows"] for name,summary in result["validation"]["tables"].items()}
        print(f"Imported synthetic bundle via {a.backend}: "+", ".join(f"{name}={count}" for name,count in counts.items()))
        for warning in result["validation"]["warnings"]: print(f"DATA QUALITY WARNING: {warning}")
    elif a.cmd=="ingest-filings":
        rows=[]
        for t in a.tickers:
            try: rows+=fetch_filings(t,get_ticker_cik(t,user_agent=config.SEC_USER_AGENT),a.start,a.end,config.SEC_USER_AGENT,config.DATA_DIR/"bronze/sec")
            except Exception as e: log.exception("Filing ingestion failed for %s: %s",t,e)
        if rows: write_table(pd.DataFrame(rows),config.DATA_DIR/"silver/filings/filings.parquet")
        print(f"Ingested {len(rows)} SEC filings")
    elif a.cmd=="ingest-prices":
        df=fetch_yfinance(a.tickers,a.start,a.end)
        if not df.empty: write_table(df,config.DATA_DIR/"silver/prices/daily_prices.parquet")
        print(f"Retrieved {len(df)} market observations; source tagged yfinance")
    elif a.cmd=="process": print("Spark transforms are available via secu_lense.spark_jobs; run demo for the local end-to-end slice.")
    elif a.cmd=="train":
        from .eda import explore
        explore(config.DATA_DIR/"gold","artifacts/eda")
        ds,_,metrics,_=run_training_workflow(config.DATA_DIR/"gold","artifacts",config.DATA_DIR/"processed/ml_training_dataset.parquet",config.NEGATIVE_RETURN_THRESHOLD)
        print(f"Trained/evaluated with chronological holdout on {len(ds)} synthetic filing events")
        for target,report in metrics.items(): print(f"{target}: {report.get('status')}; model={report.get('selected_model')}; test={report.get('models',{}).get(report.get('selected_model'),{}).get('test')}")
    elif a.cmd=="evaluate":
        path=config.DATA_DIR.parent/"artifacts/evaluation/metrics.json"
        if path.exists(): print(path.read_text(encoding="utf-8"))
        else: print("No evaluation found. Run `python -m secu_lense.cli train` first.")
    elif a.cmd=="spark-train": print(train_spark_mllib(config.DATA_DIR/"processed/ml_training_dataset.parquet","artifacts/models/spark"))
    elif a.cmd=="rag-build": print("Deterministic glossary and local filing retrieval are available without building a vector index.")
if __name__=="__main__": main()
