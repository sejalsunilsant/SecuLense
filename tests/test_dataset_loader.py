import json
import tempfile
from pathlib import Path
import pandas as pd
from secu_lense.dataset_loader import load_demo_bundle, temporal_event_returns, validate_bundle

def test_filing_event_joins_use_strictly_later_sessions_and_trading_day_horizons():
    filings=pd.DataFrame([{"ticker":"ABC","accession_number":"SYNTH-1","filing_date":"2024-01-05"}])
    prices=pd.DataFrame({"ticker":["ABC"]*5,"trade_date":pd.to_datetime(["2024-01-04","2024-01-05","2024-01-08","2024-01-09","2024-01-10"]),"close":[100,105,110,121,110],"adjusted_close":[100,105,110,121,110]})
    result=temporal_event_returns(filings,prices,horizons=(1,2,3,5))
    assert result.loc[result.horizon==1,"base_trade_date"].iloc[0]=="2024-01-05"
    assert result.loc[result.horizon==1,"event_anchor_date"].iloc[0]=="2024-01-08"
    assert abs(result.loc[result.horizon==1,"cumulative_return"].iloc[0]-(110/105-1))<1e-9
    assert result.loc[result.horizon==5,"data_quality_status"].iloc[0]=="insufficient subsequent trading sessions"

def test_loader_reads_requested_tables_and_writes_parquet():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
        root=Path(temp); source=root/"bundle"; output=root/"gold"
        (source/"prices").mkdir(parents=True); (source/"glossary").mkdir(); (source/"raw_filings").mkdir()
        (source/"manifest.json").write_text(json.dumps({"synthetic":True,"warning":"demo only"}),encoding="utf-8")
        (source/"companies.csv").write_text("ticker,company_name,cik,sector,is_synthetic_metadata\nABC,Demo Co,0000000001,Technology,True\n",encoding="utf-8")
        (source/"filings.csv").write_text("ticker,company_name,cik,accession_number,filing_type,filing_date,accepted_timestamp,fiscal_period_end,filing_url,raw_document_path,is_synthetic\nABC,Demo Co,0000000001,SYNTH-1,10-K,2024-01-05,,2023-12-31,,,True\n",encoding="utf-8")
        (source/"risk_scores.csv").write_text("ticker,accession_number,filing_type,filing_date,source_section,paragraph_id,original_paragraph,risk_category,severity_score,novelty_score,confidence_score,evidence,model_provider,is_synthetic\nABC,SYNTH-1,10-K,2024-01-05,Item 1A,p1,Test risk,supply_chain,0.7,0.8,0.9,Test risk,demo,True\n",encoding="utf-8")
        (source/"filing_diffs.csv").write_text("ticker,previous_accession,current_accession,previous_filing_date,current_filing_date,section_name,risk_category,change_type,old_text,new_text,similarity_score,is_synthetic\nABC,SYNTH-0,SYNTH-1,2023-01-01,2024-01-05,Item 1A,supply_chain,added,,Test risk,0,True\n",encoding="utf-8")
        (source/"prices/daily_prices.csv").write_text("ticker,trade_date,open,high,low,close,adjusted_close,volume,data_source,is_synthetic\nABC,2024-01-04,99,101,98,100,100,10,synthetic,True\nABC,2024-01-08,109,111,108,110,110,11,synthetic,True\n",encoding="utf-8")
        (source/"glossary/financial_glossary.csv").write_text("term,definition\nRisk,Demo definition\n",encoding="utf-8")
        (source/"glossary/educational_qa.json").write_text(json.dumps([{"question":"Q?","answer":"A.","category":"demo","difficulty":"beginner"}]),encoding="utf-8")
        (source/"raw_filings/SYNTH-1.json").write_text(json.dumps({"ticker":"ABC","accession_number":"SYNTH-1","filing_type":"10-K","filing_date":"2024-01-05","is_synthetic":True,"sections":[{"section_name":"Item 1A: Risk Factors","paragraphs":[{"paragraph_id":"p1","paragraph_text":"Test risk.","risk_category":"supply_chain"}]}]}),encoding="utf-8")
        loaded=load_demo_bundle(source,output)
        assert len(loaded["tables"]["companies"])==1
        assert len(loaded["tables"]["educational_qa"])==1
        assert len(loaded["tables"]["filing_sections"])==1
        assert (output/"event_returns.parquet").exists()
        assert (output/"validation_report.json").exists()

def test_validation_reports_invalid_dates_duplicates_and_missing_cells():
    data={"filings":pd.DataFrame({"accession_number":["a","a"],"filing_date":[pd.NaT,pd.Timestamp("2024-01-01")]})}
    report=validate_bundle(data)
    assert report["tables"]["filings"]["duplicate_keys"]==1
    assert report["tables"]["filings"]["invalid_filing_date"]==1
    assert report["tables"]["filings"]["missing_cells"]==1
