import pandas as pd
import tempfile
from pathlib import Path
from secu_lense.filings import extract_sections, compare_paragraphs, normalize_metadata
from secu_lense.analytics import analyze_risk, risk_change_score, trading_event
from secu_lense.copilot import retrieve, answer
from secu_lense.storage import initialize

def test_section_extraction_variants():
    raw="<html><body><p>ITEM 1A. Risk Factors</p><p>"+"Risk text "*50+"</p><p>ITEM 7. Management Discussion</p><p>"+"Management text "*50+"</p></body></html>"
    result=extract_sections(raw)
    assert result["Item 1A: Risk Factors"]["status"]=="complete"
    assert result["Item 7: MD&A"]["status"]=="complete"

def test_diff_and_schema_score():
    diffs=compare_paragraphs("We face competition and pricing pressure.","We face competition and pricing pressure. Suppliers may be disrupted.")
    assert diffs and diffs[0]["change_type"] in {"modified","new"}
    risk=analyze_risk("ABC","Our suppliers may experience disruptions.")
    assert risk.risk_category=="Supply chain" and 0<=risk_change_score([risk],1)<=100

def test_trading_day_horizon():
    d=pd.bdate_range("2024-01-01",periods=100)
    p=pd.DataFrame({"trade_date":d,"close":range(100,200),"adjusted_close":range(100,200)})
    result=trading_event(p,str(d[0].date()),horizons=(30,))
    assert result[0]["horizon"]==30 and result[0]["cumulative_return"]>0

def test_rag_sources_and_metadata_db():
    docs=[{"ticker":"ABC","paragraph_text":"The company depends on suppliers.","accession_number":"1"}]
    assert retrieve("supplier risk",docs) and "suppliers" in answer("supplier risk",docs)["answer"]
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
        initialize(Path(directory)/"app.db")

def test_metadata_normalization():
    r=normalize_metadata({"accessionNumber":"1","form":"10-K/A","filingDate":"2024-01-01"},"abc","12")
    assert r["ticker"]=="ABC" and r["is_amendment"] and r["cik"]=="0000000012"
