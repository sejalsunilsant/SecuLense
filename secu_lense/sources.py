"""Replaceable market-data adapter. Synthetic observations remain explicitly tagged."""
from pathlib import Path
import pandas as pd

def fetch_yfinance(tickers:list[str], start:str, end:str)->pd.DataFrame:
    import yfinance as yf
    rows=[]
    for ticker in tickers:
        frame=yf.download(ticker,start=start,end=end,auto_adjust=False,progress=False)
        if frame.empty: continue
        if isinstance(frame.columns,pd.MultiIndex): frame.columns=frame.columns.get_level_values(0)
        frame=frame.reset_index(); frame["ticker"]=ticker; frame["data_source"]="yfinance"
        frame=frame.rename(columns={"Date":"trade_date","Adj Close":"adjusted_close","Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
        rows.append(frame[["ticker","trade_date","open","high","low","close","adjusted_close","volume","data_source"]])
    return pd.concat(rows,ignore_index=True) if rows else pd.DataFrame()

def write_table(df:pd.DataFrame,path:Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    try: df.to_parquet(path,index=False)
    except ImportError: df.to_json(path.with_suffix(".jsonl"),orient="records",lines=True)

def read_table(path:Path)->pd.DataFrame:
    if path.exists(): return pd.read_parquet(path)
    json_path=path.with_suffix(".jsonl")
    return pd.read_json(json_path,lines=True) if json_path.exists() else pd.DataFrame()
