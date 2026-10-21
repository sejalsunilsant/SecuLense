import numpy as np
import pandas as pd
import tempfile
from pathlib import Path
from secu_lense.ml_pipeline import (_event_price_features, _event_targets, chronological_split,
    train_evaluate, predict_filing_risk, FIXED_FEATURES)

def test_market_features_are_cut_off_before_filing():
    dates=pd.bdate_range("2024-01-01",periods=40)
    close=np.arange(100,140,dtype=float)
    prices=pd.DataFrame({"trade_date":dates,"close":close,"adjusted_close":close,"volume":np.arange(1,41)})
    before=_event_price_features(dates[30],prices)
    prices.loc[prices.trade_date>=dates[30],"adjusted_close"]*=1000
    after=_event_price_features(dates[30],prices)
    assert before["feature_as_of_date"]==str(dates[29].date())
    assert before["previous_5_session_return"]==after["previous_5_session_return"]
    assert before["previous_20_session_return"]==after["previous_20_session_return"]

def test_targets_use_later_session_and_calendar_convention():
    dates=pd.bdate_range("2024-01-01",periods=150)
    prices=pd.DataFrame({"trade_date":dates,"adjusted_close":np.arange(100,250,dtype=float),"close":np.arange(100,250,dtype=float)})
    target=_event_targets("2024-01-10",prices,-.05)
    assert target["return_1d"]>0 and target["return_5td"]>target["return_1d"]
    # Calendar target chooses the first observed trading date at or after event date + 30 days.
    base_index=dates.get_indexer([pd.Timestamp("2024-01-09")])[0]
    end_index=next(i for i,d in enumerate(dates) if d>=pd.Timestamp("2024-02-09"))
    assert np.isclose(target["return_30cd"],prices.adjusted_close.iloc[end_index]/prices.adjusted_close.iloc[base_index]-1)
    assert target["negative_return_30d"]==0

def _training_fixture(n=80):
    rng=np.random.default_rng(18); dates=pd.date_range("2020-01-01",periods=n,freq="7D")
    data={"ticker":[f"T{i%5}" for i in range(n)],"accession_number":[f"SYNTH-{i}" for i in range(n)],"filing_date":dates,
          "negative_return_30d":np.array([i%2 for i in range(n)]),"sector":["Tech" if i%2 else "Health" for i in range(n)],"filing_type":["10-K" if i%3 else "10-Q" for i in range(n)]}
    for f in FIXED_FEATURES:
        if f not in data: data[f]=rng.normal(size=n)
    data["risk_category_supply_chain"]=rng.integers(0,4,n)
    return pd.DataFrame(data)

def test_purged_chronological_split_has_no_random_future_training():
    data=_training_fixture(); split=chronological_split(data,"negative_return_30d",purge_days=30)
    assert split["train"].filing_date.max()<split["validation"].filing_date.min()
    assert split["validation"].filing_date.max()<split["test"].filing_date.min()
    assert (split["validation"].filing_date.min()-split["train"].filing_date.max()).days>=30

def test_model_training_serialization_schema_and_prediction():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
        tmp_path=Path(directory); data=_training_fixture(); processed=tmp_path/"processed"; processed.mkdir(); data.to_parquet(processed/"ml_training_dataset.parquet",index=False)
        artifacts=tmp_path/"artifacts"
        results,metadata=train_evaluate(data,artifacts,targets=["negative_return_30d"],purge_days=30)
        target=metadata["targets"]["negative_return_30d"]
        assert target["trained_model_names"]
        assert target["model_artifacts"]
        assert target["test_evaluation_sufficient"] is True
        pred=predict_filing_risk(data.ticker.iloc[-1],data.accession_number.iloc[-1],"30d",data_dir=tmp_path/"gold",artifacts_dir=artifacts)
        assert pred["status"]=="available" and 0<=pred["predicted_probability"]<=1
        missing=predict_filing_risk("NOPE","missing","30d",data_dir=tmp_path/"gold",artifacts_dir=artifacts)
        assert missing["status"]=="filing_not_found" or missing["status"]=="training_dataset_missing"
