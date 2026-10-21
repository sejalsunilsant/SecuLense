"""Load the packaged synthetic demo bundle, validate it, and persist Parquet tables."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

CSV_FILES={"companies":"companies.csv","filings":"filings.csv","risk_scores":"risk_scores.csv","filing_diffs":"filing_diffs.csv","daily_prices":"prices/daily_prices.csv","financial_glossary":"glossary/financial_glossary.csv"}
DATE_COLUMNS={"filings":["filing_date","accepted_timestamp","fiscal_period_end"],"risk_scores":["filing_date"],"filing_diffs":["previous_filing_date","current_filing_date"],"daily_prices":["trade_date"]}
REQUIRED_COLUMNS={"companies":["ticker","company_name","cik"],"filings":["ticker","accession_number","filing_type","filing_date"],
  "risk_scores":["ticker","accession_number","paragraph_id","risk_category","severity_score","novelty_score","confidence_score"],
  "filing_diffs":["ticker","previous_accession","current_accession","change_type","old_text","new_text"],
  "daily_prices":["ticker","trade_date","close"],"financial_glossary":["term","definition"],"educational_qa":["question","answer"]}
NUMERIC_COLUMNS={"risk_scores":["severity_score","novelty_score","confidence_score"],"filing_diffs":["similarity_score"],"daily_prices":["open","high","low","close","adjusted_close","volume"]}

def temporal_event_returns(filings:pd.DataFrame,prices:pd.DataFrame,horizons=(1,5,30,60,90))->pd.DataFrame:
    """Close-to-close filing event returns measured only on later trading sessions.

    Baseline is the last available close on or before the filing date. Horizon 1 is
    the first price session strictly after the filing date; weekends/holidays require
    no calendar-day arithmetic. Insufficient horizons are retained with null returns.
    """
    result=[]
    f=filings.copy(); p=prices.copy()
    f["filing_date"]=pd.to_datetime(f["filing_date"],errors="coerce").dt.normalize()
    p["trade_date"]=pd.to_datetime(p["trade_date"],errors="coerce").dt.normalize()
    price_col="adjusted_close" if "adjusted_close" in p.columns else "close"
    for ticker,filing_group in f.groupby("ticker",sort=False):
        px=p[p.ticker==ticker].dropna(subset=["trade_date",price_col]).sort_values("trade_date")
        dates=px.trade_date.to_numpy(dtype="datetime64[ns]"); vals=pd.to_numeric(px[price_col],errors="coerce").to_numpy(dtype=float)
        if not len(dates):
            for filing in filing_group.itertuples(index=False):
                for h in horizons: result.append(_empty_event(filing,h,"no ticker price history"))
            continue
        for filing in filing_group.itertuples(index=False):
            fd=filing.filing_date
            if pd.isna(fd):
                for h in horizons: result.append(_empty_event(filing,h,"invalid filing date"))
                continue
            base=int(np.searchsorted(dates,np.datetime64(fd),side="right")-1)
            for h in horizons:
                target=base+h
                if base<0:
                    result.append(_empty_event(filing,h,"no close on/before filing date")); continue
                if target>=len(dates):
                    row=_empty_event(filing,h,"insufficient subsequent trading sessions")
                    row.update(base_trade_date=pd.Timestamp(dates[base]).date().isoformat(),event_anchor_date=None)
                    result.append(row); continue
                window=vals[base:target+1]
                dd=float(np.min(window/np.maximum.accumulate(window)-1))
                result.append({"ticker":ticker,"accession_number":filing.accession_number,"filing_date":fd.date().isoformat(),
                  "base_trade_date":pd.Timestamp(dates[base]).date().isoformat(),"event_anchor_date":pd.Timestamp(dates[base+1]).date().isoformat(),
                  "horizon":int(h),"cumulative_return":float(vals[target]/vals[base]-1),"maximum_drawdown":dd,
                  "data_quality_status":"complete","data_source":"SYNTHETIC_DEMO"})
    return pd.DataFrame(result)

def _empty_event(filing,h,status):
    fd=getattr(filing,"filing_date",None)
    fd=None if pd.isna(fd) else pd.Timestamp(fd).date().isoformat()
    return {"ticker":filing.ticker,"accession_number":filing.accession_number,"filing_date":fd,
            "base_trade_date":None,"event_anchor_date":None,"horizon":int(h),"cumulative_return":None,"maximum_drawdown":None,
            "data_quality_status":status,"data_source":"SYNTHETIC_DEMO"}

def _read_pandas(source:Path)->dict[str,Any]:
    data={name:pd.read_csv(source/filename,dtype={"cik":str,"accession_number":str}) for name,filename in CSV_FILES.items()}
    for name,columns in DATE_COLUMNS.items():
        for column in columns:
            if column in data[name]: data[name][column]=pd.to_datetime(data[name][column],errors="coerce")
    qa=json.loads((source/"glossary/educational_qa.json").read_text(encoding="utf-8"))
    data["educational_qa"]=pd.DataFrame(qa)
    paragraphs=[]
    for path in sorted((source/"raw_filings").glob("*.json")):
        filing=json.loads(path.read_text(encoding="utf-8"))
        for section in filing.get("sections",[]):
            for paragraph in section.get("paragraphs",[]):
                paragraphs.append({"ticker":filing.get("ticker"),"accession_number":filing.get("accession_number"),
                    "filing_type":filing.get("filing_type"),"filing_date":filing.get("filing_date"),
                    "section_name":section.get("section_name",paragraph.get("section_name")),"paragraph_id":paragraph.get("paragraph_id"),
                    "paragraph_text":paragraph.get("paragraph_text"),"risk_category":paragraph.get("risk_category"),
                    "is_synthetic":bool(filing.get("is_synthetic",False))})
    data["filing_sections"]=pd.DataFrame(paragraphs,columns=["ticker","accession_number","filing_type","filing_date","section_name","paragraph_id","paragraph_text","risk_category","is_synthetic"])
    return data

def validate_bundle(data:dict[str,pd.DataFrame])->dict:
    key_cols={"companies":["ticker"],"filings":["accession_number"],"risk_scores":["ticker","accession_number","paragraph_id"],
              "filing_diffs":["ticker","previous_accession","current_accession","section_name","change_type","old_text","new_text"],"daily_prices":["ticker","trade_date"]}
    report={"synthetic":True,"tables":{},"warnings":[],"identifier_checks":{}}
    for name,df in data.items():
        table={"rows":int(len(df)),"missing_cells":int(df.isna().sum().sum()),"duplicate_rows":int(df.duplicated().sum())}
        required=REQUIRED_COLUMNS.get(name,[])
        table["missing_required_columns"]=[c for c in required if c not in df.columns]
        numeric=NUMERIC_COLUMNS.get(name,[])
        table["invalid_numeric_values"]={}
        table["out_of_range_values"]={}
        for column in numeric:
            if column in df:
                original=df[column].notna()
                converted=pd.to_numeric(df[column],errors="coerce")
                table["invalid_numeric_values"][column]=int((original&converted.isna()).sum())
                df[column]=converted
                if name=="risk_scores" and column in {"severity_score","novelty_score","confidence_score"}:
                    table["out_of_range_values"][column]=int(((converted<0)|(converted>1)).sum())
        if name=="daily_prices" and {"low","high"}.issubset(df.columns):
            table["invalid_ohlc_rows"]=int((pd.to_numeric(df.low,errors="coerce")>pd.to_numeric(df.high,errors="coerce")).sum())
        if name in key_cols:
            keys=[c for c in key_cols[name] if c in df]
            table["duplicate_keys"]=int(df.duplicated(keys).sum()) if keys else 0
        if name in DATE_COLUMNS:
            for col in DATE_COLUMNS[name]:
                if col in df: table[f"invalid_{col}"]=int(df[col].isna().sum())
        report["tables"][name]=table
        if table["duplicate_rows"]: report["warnings"].append(f"{name}: {table['duplicate_rows']} duplicate rows")
        if table.get("duplicate_keys"): report["warnings"].append(f"{name}: {table['duplicate_keys']} duplicate primary keys")
        if table["missing_cells"]: report["warnings"].append(f"{name}: {table['missing_cells']} missing cells (review nullable fields and required identifiers)")
        if table["missing_required_columns"]: report["warnings"].append(f"{name}: missing required columns: {', '.join(table['missing_required_columns'])}")
        invalid_numeric=sum(table["invalid_numeric_values"].values())
        if invalid_numeric: report["warnings"].append(f"{name}: {invalid_numeric} invalid numeric values")
        out_of_range=sum(table["out_of_range_values"].values())
        if out_of_range: report["warnings"].append(f"{name}: {out_of_range} out-of-range score values")
        if table.get("invalid_ohlc_rows"): report["warnings"].append(f"{name}: {table['invalid_ohlc_rows']} OHLC rows have low > high")
        for key,val in table.items():
            if key.startswith("invalid_") and isinstance(val,(int,float)) and val>0: report["warnings"].append(f"{name}: {val} invalid {key[8:]} values")
    if "companies" in data and "filings" in data:
        company_tickers=set(data["companies"].ticker.dropna().astype(str)); filing_tickers=set(data["filings"].ticker.dropna().astype(str))
        missing_tickers=sorted(filing_tickers-company_tickers)
        report["identifier_checks"]["filings_without_company"]=missing_tickers
        if missing_tickers: report["warnings"].append(f"Filings reference unknown companies: {', '.join(missing_tickers)}")
        if "risk_scores" in data:
            keys=set(zip(data["filings"].ticker.astype(str),data["filings"].accession_number.astype(str)))
            orphan=data["risk_scores"].loc[~data["risk_scores"].apply(lambda r:(str(r.ticker),str(r.accession_number)) in keys,axis=1)]
            report["identifier_checks"]["risk_scores_without_filing"]=int(len(orphan))
            if len(orphan): report["warnings"].append(f"Risk records reference {len(orphan)} unknown filing identifiers")
        if "filing_diffs" in data:
            filing_keys=set(zip(data["filings"].ticker.astype(str),data["filings"].accession_number.astype(str)))
            current_ok=data["filing_diffs"].apply(lambda r:(str(r.ticker),str(r.current_accession)) in filing_keys,axis=1)
            previous_ok=data["filing_diffs"].apply(lambda r:(str(r.ticker),str(r.previous_accession)) in filing_keys,axis=1)
            report["identifier_checks"]["diffs_with_unknown_current_filing"]=int((~current_ok).sum())
            report["identifier_checks"]["diffs_with_unknown_previous_filing"]=int((~previous_ok).sum())
            if (~current_ok).any(): report["warnings"].append(f"Filing diffs have {(~current_ok).sum()} current accession/ticker pairs not in filings")
            if (~previous_ok).any(): report["warnings"].append(f"Filing diffs have {(~previous_ok).sum()} previous accession/ticker pairs not in filings")
        if "cik" in data["companies"] and "cik" in data["filings"]:
            company_cik=data["companies"].drop_duplicates("ticker").set_index("ticker").cik.astype(str).to_dict()
            mismatch=data["filings"].apply(lambda r:str(r.cik)!=str(company_cik.get(r.ticker)),axis=1)
            report["identifier_checks"]["filing_company_cik_mismatches"]=int(mismatch.sum())
            if mismatch.any(): report["warnings"].append(f"{int(mismatch.sum())} filing records have CIK values inconsistent with company metadata")
    if "companies" in data and "daily_prices" in data:
        unknown=sorted(set(data["daily_prices"].ticker.dropna().astype(str))-set(data["companies"].ticker.dropna().astype(str)))
        report["identifier_checks"]["prices_without_company"]=unknown
        if unknown: report["warnings"].append(f"Prices reference unknown companies: {', '.join(unknown)}")
    return report

def _write_pandas(data:dict[str,pd.DataFrame],destination:Path):
    destination.mkdir(parents=True,exist_ok=True)
    for name,df in data.items(): df.to_parquet(destination/f"{name}.parquet",index=False)

def load_demo_bundle(source:Path|str,destination:Path|str,backend="pandas",spark=None)->dict:
    source,destination=Path(source),Path(destination)
    manifest_path=source/"manifest.json"
    if not manifest_path.is_file(): raise FileNotFoundError(f"No manifest.json in dataset bundle: {source}")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("synthetic") is not True: raise ValueError("Only a manifest-marked synthetic bundle can use this demo loader")
    if backend not in {"pandas","pyspark"}: raise ValueError("backend must be 'pandas' or 'pyspark'")
    if backend=="pyspark":
        if spark is None:
            try:
                from pyspark.sql import SparkSession
            except ImportError as exc: raise RuntimeError("Install pyspark to use backend='pyspark'") from exc
            spark=SparkSession.builder.appName("SecuLenseDemoLoader").getOrCreate()
        tables={name:spark.read.option("header",True).option("inferSchema",True).csv(str(source/file)) for name,file in CSV_FILES.items()}
        for name in ("companies","filings"):
            if "cik" in tables[name].columns:
                from pyspark.sql import functions as F
                tables[name]=tables[name].withColumn("cik",F.lpad(F.col("cik").cast("string"),10,"0"))
        tables["educational_qa"]=spark.read.json(str(source/"glossary/educational_qa.json"))
        from pyspark.sql import functions as F
        raw=spark.read.option("multiLine",True).json(str(source/"raw_filings/*.json"))
        expanded=raw.select("ticker","accession_number","filing_type","filing_date","is_synthetic",F.explode("sections").alias("section"))
        expanded=expanded.select("ticker","accession_number","filing_type","filing_date","is_synthetic","section.section_name",F.explode("section.paragraphs").alias("paragraph"))
        tables["filing_sections"]=expanded.select("ticker","accession_number","filing_type","filing_date","is_synthetic","section_name","paragraph.paragraph_id","paragraph.paragraph_text","paragraph.risk_category")
        # Spark validates and writes source tables in distributed form. Event math below
        # uses the shared, deterministic pandas implementation on this compact demo set.
        destination.mkdir(parents=True,exist_ok=True)
        for name,df in tables.items(): df.write.mode("overwrite").parquet(str(destination/f"{name}.parquet"))
        local=_read_pandas(source)
        report=validate_bundle(local)
        local["event_returns"]=temporal_event_returns(local["filings"],local["daily_prices"])
        local["event_returns"].to_parquet(destination/"event_returns.parquet",index=False)
        report["tables"]["event_returns"]={"rows":len(local["event_returns"]),"duplicate_rows":int(local["event_returns"].duplicated().sum())}
        (destination/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        (destination/"validation_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        return {"backend":"pyspark","tables":tables,"validation":report,"manifest":manifest,"spark":spark}
    data=_read_pandas(source)
    report=validate_bundle(data)
    data["event_returns"]=temporal_event_returns(data["filings"],data["daily_prices"])
    report["tables"]["event_returns"]={"rows":int(len(data["event_returns"])),"missing_cells":int(data["event_returns"].isna().sum().sum()),"duplicate_rows":int(data["event_returns"].duplicated().sum())}
    _write_pandas(data,destination)
    (destination/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    (destination/"validation_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return {"backend":"pandas","tables":data,"validation":report,"manifest":manifest}
