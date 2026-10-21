"""Deterministic risk features and trading-day event study calculations."""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

CATEGORIES={
"Debt and liquidity":["debt","liquidity","covenant","credit facility","refinanc"],
"Regulatory and legal":["regulat","litigation","investigation","compliance","legal"],
"Supply chain":["supplier","supply chain","manufactur","shortage","logistics"],
"Customer concentration and churn":["customer concentration","churn","renewal","customer loss"],
"Margin compression":["gross margin","operating margin","pricing pressure","cost inflation"],
"Revenue recognition and receivables":["accounts receivable","revenue recognition","collection","payment terms"],
"Cybersecurity and data privacy":["cyber","data breach","privacy","ransomware"],
"Competition and market demand":["competition","competitive","demand","market adoption"],
"Operational disruptions":["disruption","outage","business continuity","operational"],
"Foreign exchange and macroeconomic exposure":["foreign exchange","currency","inflation","macroeconomic","interest rates"],
"Capital expenditure and investment":["capital expenditure","capital spending","investment","infrastructure"],}

class RiskRecord(BaseModel):
    ticker:str; accession_number:str="demo"; filing_type:str="10-K"; filing_date:str=""
    source_section:str="Item 1A: Risk Factors"; original_paragraph:str
    previous_paragraph:str|None=None; risk_category:str; risk_description:str
    severity_score:float=Field(ge=0,le=1); novelty_score:float=Field(ge=0,le=1)
    evidence:str; source_paragraph_reference:str=""; confidence_score:float=Field(ge=0,le=1)
    model_provider:str="deterministic"; processing_status:str="complete"

def classify_risk(text:str)->str:
    lower=text.lower(); hits=[(sum(lower.count(k) for k in keys),cat) for cat,keys in CATEGORIES.items()]
    n,cat=max(hits,default=(0,"Other or uncertain"))
    return cat if n else "Other or uncertain"

def analyze_risk(ticker:str,text:str,previous:str|None=None,accession="demo",filing_date="") -> RiskRecord:
    category=classify_risk(text); terms=CATEGORIES.get(category,[])
    evidence=next((sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+",text) if any(t in sentence.lower() for t in terms)),text[:240])
    severity=min(1.0,0.25+0.12*sum(x in text.lower() for x in ("material","significant","substantial","could adversely","unable","critical")))
    novelty=0.85 if previous is None else max(0.1,1-min(1,len(set(text.lower().split())&set(previous.lower().split()))/max(1,len(set(text.lower().split())))))
    return RiskRecord(ticker=ticker,accession_number=accession,filing_date=filing_date,original_paragraph=text,previous_paragraph=previous,
       risk_category=category,risk_description=text[:300],severity_score=severity,novelty_score=novelty,evidence=evidence,
       source_paragraph_reference=f"{accession}:Item1A",confidence_score=0.58 if category!="Other or uncertain" else 0.3)

def risk_change_score(records:list[RiskRecord], changed_paragraphs:int=0, completeness=1.0)->float:
    if not records and not changed_paragraphs:return 0.0
    severity=np.mean([r.severity_score for r in records]) if records else 0
    novelty=np.mean([r.novelty_score for r in records]) if records else 0
    # Published, configurable baseline: severity 50%, novelty 30%, volume 20% (saturates at 5).
    volume=min(1,changed_paragraphs/5)
    return round(100*(.5*severity+.3*novelty+.2*volume)*max(0,min(1,completeness)),1)

def trading_event(prices:pd.DataFrame, anchor_date, horizons=(30,60,90), benchmark:pd.DataFrame|None=None)->list[dict]:
    p=prices.copy(); p["trade_date"]=pd.to_datetime(p.trade_date); p=p.sort_values("trade_date").reset_index(drop=True)
    anchor=pd.Timestamp(anchor_date); start=p.index[p.trade_date>=anchor]
    if len(start)==0:return []
    i=int(start[0]); out=[]
    for h in horizons:
        j=i+h
        if j>=len(p):out.append({"horizon":h,"cumulative_return":None,"maximum_drawdown":None,"data_quality_status":"insufficient forward prices"});continue
        series=p.adjusted_close if "adjusted_close" in p else p.close
        window=series.iloc[i:j+1].astype(float); ret=float(window.iloc[-1]/window.iloc[0]-1)
        dd=float((window/window.cummax()-1).min())
        out.append({"horizon":h,"event_anchor_date":str(p.trade_date.iloc[i].date()),"cumulative_return":ret,"maximum_drawdown":dd,"data_quality_status":"complete"})
    return out

def build_features(diffs:list[dict],records:list[RiskRecord])->dict:
    return {"new_risks":len(records),"modified_paragraphs":sum(d["change_type"]=="modified" for d in diffs),
            "mean_severity":float(np.mean([r.severity_score for r in records])) if records else 0.0,
            "mean_novelty":float(np.mean([r.novelty_score for r in records])) if records else 0.0}
