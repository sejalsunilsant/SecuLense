"""Reproducible exploratory report and plots for SecuLense synthetic data."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

def explore(data_dir="data/gold",output_dir="artifacts/eda"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root=Path(data_dir); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    names=("companies","filings","risk_scores","filing_diffs","daily_prices")
    tables={n:pd.read_parquet(root/f"{n}.parquet") for n in names}
    companies,filings,risks,diffs,prices=(tables[n] for n in names)
    manifest_path=root/"manifest.json"; manifest=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"synthetic":True,"dataset_name":"unknown"}
    stats={"dataset":manifest.get("dataset_name"),"synthetic":True,"warning":"Synthetic demo content and prices; no real SEC/market claim.",
      "companies":int(companies.ticker.nunique()),"filings":int(len(filings)),"risk_records":int(len(risks)),"filing_comparisons":int(len(diffs)),"daily_price_observations":int(len(prices)),
      "missing_by_table":{k:{c:int(v) for c,v in df.isna().sum().items() if v} for k,df in tables.items()},
      "risk_category_distribution":risks.risk_category.value_counts(dropna=False).to_dict(),
      "risk_severity_summary":pd.to_numeric(risks.severity_score,errors="coerce").describe().to_dict(),
      "filing_frequency":filings.groupby(["ticker","filing_type"]).size().rename("filings").reset_index().to_dict("records")}
    prices["trade_date"]=pd.to_datetime(prices.trade_date,errors="coerce"); prices["adjusted_close"]=pd.to_numeric(prices.adjusted_close,errors="coerce").fillna(pd.to_numeric(prices.close,errors="coerce"))
    prices=prices.sort_values(["ticker","trade_date"]); prices["daily_return"]=prices.groupby("ticker").adjusted_close.pct_change(); prices["rolling_20d_volatility"]=prices.groupby("ticker").daily_return.transform(lambda x:x.rolling(20,min_periods=5).std())
    stats["daily_return_summary"]=prices.daily_return.replace([np.inf,-np.inf],np.nan).describe().to_dict()
    stats["rolling_20_session_volatility_summary"]=prices.rolling_20d_volatility.describe().to_dict()
    (out/"eda_report.json").write_text(json.dumps(stats,indent=2,default=_json_default),encoding="utf-8")
    lines=["# SecuLense EDA report","","**SYNTHETIC DEMONSTRATION DATA ONLY** — filing content, scores, and prices are simulated.","",f"- Companies: {stats['companies']}",f"- Filing records: {stats['filings']}",f"- Risk records: {stats['risk_records']}",f"- Filing comparisons: {stats['filing_comparisons']}",f"- Daily price observations: {stats['daily_price_observations']}","", "## Risk categories", ""]
    lines += [f"- {k}: {v}" for k,v in stats["risk_category_distribution"].items()]
    lines += ["", "## Missing data", "", "```json",json.dumps(stats["missing_by_table"],indent=2),"```", "", "Returns and volatility are calculated from the supplied synthetic adjusted-close series. These summaries are software checks, not empirical findings."]
    (out/"eda_report.md").write_text("\n".join(lines),encoding="utf-8")
    fig,ax=plt.subplots(figsize=(9,4)); risks.risk_category.value_counts().sort_values().plot.barh(ax=ax,color="#5183a8"); ax.set_title("Synthetic risk records by category"); fig.tight_layout(); fig.savefig(out/"risk_categories.png",dpi=140); plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4)); pd.to_numeric(risks.severity_score,errors="coerce").dropna().plot.hist(ax=ax,bins=15,color="#8a66a8"); ax.set_title("Synthetic risk severity distribution"); fig.tight_layout(); fig.savefig(out/"risk_severity.png",dpi=140); plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4)); prices.daily_return.dropna().plot.hist(ax=ax,bins=40,color="#48937e"); ax.set_title("Synthetic daily return distribution"); fig.tight_layout(); fig.savefig(out/"daily_returns.png",dpi=140); plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4)); prices.rolling_20d_volatility.dropna().plot.hist(ax=ax,bins=30,color="#d08742"); ax.set_title("Synthetic 20-session volatility distribution"); fig.tight_layout(); fig.savefig(out/"rolling_volatility.png",dpi=140); plt.close(fig)
    frequency=filings.groupby(["ticker","filing_type"]).size().unstack(fill_value=0); ax=frequency.plot.bar(figsize=(10,4)); ax.set_title("Synthetic filing frequency by company and form"); ax.set_ylabel("Filings"); ax.figure.tight_layout(); ax.figure.savefig(out/"filing_frequency.png",dpi=140); plt.close(ax.figure)
    missing=pd.Series({f"{t}.{c}":v for t,x in stats["missing_by_table"].items() for c,v in x.items()}); fig,ax=plt.subplots(figsize=(9,4));
    if len(missing): missing.sort_values().plot.barh(ax=ax,color="#b65e5e"); ax.set_title("Missing values by table and column"); fig.tight_layout(); fig.savefig(out/"missing_values.png",dpi=140)
    plt.close(fig)
    return stats

def _json_default(x):
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.floating,)): return None if not np.isfinite(x) else float(x)
    if hasattr(x,"isoformat"): return x.isoformat()
    return str(x)
