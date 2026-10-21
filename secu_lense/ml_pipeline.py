"""Leakage-aware filing-event dataset, chronological model evaluation, and prediction."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SYNTHETIC_WARNING="Synthetic demonstration only; no model result establishes real-world financial predictability."
HORIZONS={"30d":("negative_return_30d",30),"60d":("negative_return_60d",60),"90d":("negative_return_90d",90)}
FIXED_FEATURES=["filing_type","sector","number_of_changed_paragraphs","number_of_added_risks","number_of_modified_risks","number_of_removed_risks","number_of_unique_risk_categories","mean_severity_score","maximum_severity_score","mean_novelty_score","mean_confidence_score","weighted_risk_change_score","previous_5_session_return","previous_20_session_return","previous_20_session_volatility","previous_20_session_mean_volume","previous_20_session_volume_std"]
TARGET_COLUMNS=["return_1d","return_5td","return_30cd","return_60cd","return_90cd","maximum_drawdown_30cd","maximum_drawdown_60cd","maximum_drawdown_90cd","negative_return_30d","negative_return_60d","negative_return_90d"]

def _event_price_features(filing_date, price_frame:pd.DataFrame)->dict:
    p=price_frame.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    pxcol="adjusted_close" if "adjusted_close" in p.columns and p.adjusted_close.notna().any() else "close"
    p[pxcol]=pd.to_numeric(p[pxcol],errors="coerce")
    if pxcol=="adjusted_close" and "close" in p: p[pxcol]=p[pxcol].fillna(pd.to_numeric(p.close,errors="coerce"))
    dates=pd.to_datetime(p.trade_date,errors="coerce").dt.normalize().to_numpy(dtype="datetime64[ns]")
    values=p[pxcol].to_numpy(dtype=float)
    volumes=pd.to_numeric(p.volume,errors="coerce").to_numpy(dtype=float) if "volume" in p else np.full(len(p),np.nan)
    fd=pd.to_datetime(filing_date,errors="coerce")
    if pd.isna(fd): return {"feature_as_of_date":None,"base_trade_date":None,**{k:np.nan for k in FIXED_FEATURES if k.startswith("previous_")}}
    # Conservative: information cutoff is strictly before filing date, even if accepted time is available.
    base=int(np.searchsorted(dates,np.datetime64(fd.normalize()),side="left")-1)
    if base<0: return {"feature_as_of_date":None,"base_trade_date":None,**{k:np.nan for k in FIXED_FEATURES if k.startswith("previous_")}}
    ret5=values[base]/values[base-5]-1 if base>=5 and values[base-5] else np.nan
    ret20=values[base]/values[base-20]-1 if base>=20 and values[base-20] else np.nan
    daily_returns=pd.Series(values[:base+1]).pct_change().replace([np.inf,-np.inf],np.nan).dropna()
    vol20=float(daily_returns.tail(20).std(ddof=1)) if len(daily_returns.tail(20))>=2 else np.nan
    volwindow=pd.Series(volumes[max(0,base-19):base+1]).dropna()
    return {"feature_as_of_date":pd.Timestamp(dates[base]).date().isoformat(),"base_trade_date":pd.Timestamp(dates[base]).date().isoformat(),
       "previous_5_session_return":float(ret5) if np.isfinite(ret5) else np.nan,
       "previous_20_session_return":float(ret20) if np.isfinite(ret20) else np.nan,
       "previous_20_session_volatility":vol20,
       "previous_20_session_mean_volume":float(volwindow.mean()) if len(volwindow) else np.nan,
       "previous_20_session_volume_std":float(volwindow.std(ddof=1)) if len(volwindow)>=2 else np.nan}

def _event_targets(filing_date,price_frame:pd.DataFrame,threshold=-0.05)->dict:
    p=price_frame.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    pxcol="adjusted_close" if "adjusted_close" in p.columns and p.adjusted_close.notna().any() else "close"
    p[pxcol]=pd.to_numeric(p[pxcol],errors="coerce")
    if pxcol=="adjusted_close" and "close" in p: p[pxcol]=p[pxcol].fillna(pd.to_numeric(p.close,errors="coerce"))
    dates=pd.to_datetime(p.trade_date,errors="coerce").dt.normalize().to_numpy(dtype="datetime64[ns]"); values=p[pxcol].to_numpy(dtype=float)
    fd=pd.to_datetime(filing_date,errors="coerce")
    targets={}
    target_specs={"1d":("return_1d",1),"5td":("return_5td",5)}
    if pd.isna(fd):
        for suffix,(col,_) in target_specs.items(): targets[col]=np.nan
        for days in (30,60,90): targets[f"return_{days}cd"]=np.nan; targets[f"maximum_drawdown_{days}cd"]=np.nan
        return targets
    base=int(np.searchsorted(dates,np.datetime64(fd.normalize()),side="left")-1)
    def calc(end):
        if base<0 or end>=len(values) or end<=base or not np.isfinite(values[base]) or values[base]==0:return np.nan,np.nan
        window=values[base:end+1]
        return float(values[end]/values[base]-1),float(np.min(window/np.maximum.accumulate(window)-1))
    first_future=int(np.searchsorted(dates,np.datetime64(fd.normalize()),side="right"))
    for _,(col,h) in target_specs.items():
        end=first_future+h-1
        targets[col]=calc(end)[0]
    for days in (30,60,90):
        cutoff=np.datetime64((fd.normalize()+pd.Timedelta(days=days)).to_datetime64())
        end=int(np.searchsorted(dates,cutoff,side="left"))
        ret,dd=calc(end)
        targets[f"return_{days}cd"]=ret; targets[f"maximum_drawdown_{days}cd"]=dd
        targets[f"negative_return_{days}d"]=int(ret<threshold) if np.isfinite(ret) else np.nan
    return targets

def build_ml_dataset(data_dir:Path|str,output_path:Path|str|None=None,threshold=-0.05)->tuple[pd.DataFrame,dict]:
    root=Path(data_dir)
    def read(name):
        path=root/f"{name}.parquet"
        if not path.exists(): raise FileNotFoundError(f"Expected analytical table: {path}")
        return pd.read_parquet(path)
    filings=read("filings"); risks=read("risk_scores"); diffs=read("filing_diffs"); prices=read("daily_prices"); companies=read("companies")
    filings["filing_date"]=pd.to_datetime(filings.filing_date,errors="coerce").dt.normalize()
    prices["trade_date"]=pd.to_datetime(prices.trade_date,errors="coerce").dt.normalize()
    risks=risks.copy(); diffs=diffs.copy()
    # Event-level aggregates use only this filing's disclosed content, never later filings.
    risk_group=risks.groupby(["ticker","accession_number"],dropna=False)
    risk_base=risk_group.agg(mean_severity_score=("severity_score","mean"),maximum_severity_score=("severity_score","max"),
        mean_novelty_score=("novelty_score","mean"),mean_confidence_score=("confidence_score","mean"),
        number_of_unique_risk_categories=("risk_category","nunique"),number_of_risks=("risk_category","size")).reset_index()
    cats=pd.crosstab([risks.ticker,risks.accession_number],risks.risk_category).add_prefix("risk_category_").reset_index()
    risk_base=risk_base.merge(cats,on=["ticker","accession_number"],how="left")
    d=diffs.copy(); d["_change"]=d.change_type.astype(str).str.lower()
    d["_added"]=d._change.isin(["added","new"]).astype(int); d["_modified"]=d._change.eq("modified").astype(int); d["_removed"]=d._change.eq("removed").astype(int)
    diff_base=d.groupby(["ticker","current_accession"],dropna=False).agg(number_of_changed_paragraphs=("change_type","size"),number_of_added_risks=("_added","sum"),number_of_modified_risks=("_modified","sum"),number_of_removed_risks=("_removed","sum"),diff_risk_categories=("risk_category","nunique")).reset_index().rename(columns={"current_accession":"accession_number"})
    companies=companies[[c for c in ["ticker","sector"] if c in companies]].drop_duplicates("ticker")
    rows=[]; price_map={t:g for t,g in prices.groupby("ticker",sort=False)}
    for filing in filings.itertuples(index=False):
        fd=filing.filing_date; ticker=filing.ticker; acc=filing.accession_number
        risk_row=risk_base[(risk_base.ticker==ticker)&(risk_base.accession_number==acc)]
        diff_row=diff_base[(diff_base.ticker==ticker)&(diff_base.accession_number==acc)]
        r=risk_row.iloc[0].to_dict() if not risk_row.empty else {}
        dr=diff_row.iloc[0].to_dict() if not diff_row.empty else {}
        company=companies[companies.ticker==ticker]
        market=_event_price_features(fd,price_map.get(ticker,prices.iloc[:0]))
        target=_event_targets(fd,price_map.get(ticker,prices.iloc[:0]),threshold)
        cats_count={c:int(r.get(c,0) or 0) for c in risk_base.columns if c.startswith("risk_category_")}
        severity=r.get("mean_severity_score",np.nan); novelty=r.get("mean_novelty_score",np.nan)
        row={"ticker":ticker,"accession_number":acc,"filing_date":fd,"filing_type":getattr(filing,"filing_type",None),
          "sector":company.iloc[0].get("sector") if not company.empty else None,
          "number_of_changed_paragraphs":int(dr.get("number_of_changed_paragraphs",0) or 0),
          "number_of_added_risks":int(dr.get("number_of_added_risks",0) or 0),"number_of_modified_risks":int(dr.get("number_of_modified_risks",0) or 0),"number_of_removed_risks":int(dr.get("number_of_removed_risks",0) or 0),
          "number_of_unique_risk_categories":int(r.get("number_of_unique_risk_categories",0) or 0),"mean_severity_score":severity,"maximum_severity_score":r.get("maximum_severity_score",np.nan),
          "mean_novelty_score":novelty,"mean_confidence_score":r.get("mean_confidence_score",np.nan),
          "weighted_risk_change_score":float(100*(.6*severity+.4*novelty)) if pd.notna(severity) and pd.notna(novelty) else np.nan,
          "feature_as_of_date":market.get("feature_as_of_date"),"base_trade_date":market.get("base_trade_date"),**{k:v for k,v in market.items() if k.startswith("previous_")},**cats_count,**target,
          "data_source":"SYNTHETIC_DEMO"}
        row["negative_return_30d"]=target.get("negative_return_30d",np.nan); row["negative_return_60d"]=target.get("negative_return_60d",np.nan); row["negative_return_90d"]=target.get("negative_return_90d",np.nan)
        rows.append(row)
    dataset=pd.DataFrame(rows).sort_values(["filing_date","ticker"]).reset_index(drop=True)
    # Exclude no events silently: retain all filing events, with null targets and explicit status.
    dataset["event_quality_status"]=np.where(dataset["return_30cd"].notna(),"target_available","insufficient forward price history")
    all_features=FIXED_FEATURES+[c for c in dataset.columns if c.startswith("risk_category_")]
    dictionary={c:{"role":"feature","description":_feature_description(c)} for c in all_features}
    dictionary.update({c:{"role":"target","description":_target_description(c,threshold)} for c in TARGET_COLUMNS})
    dictionary.update({c:{"role":"identifier_or_audit","description":desc} for c,desc in {"ticker":"Company ticker; excluded from model features.","accession_number":"Filing accession; excluded from model features.","filing_date":"Filing date; used for chronological split and event alignment.","feature_as_of_date":"Last historical date used by market features.","base_trade_date":"Last close strictly before filing date used as return baseline.","event_quality_status":"Forward-price completeness status.","data_source":"Source provenance."}.items()})
    dictionary["negative_return_30d"]={"role":"target","description":f"1 when return_30cd is below {threshold:.1%}; null when unavailable."}
    dictionary["negative_return_60d"]={"role":"target","description":f"1 when return_60cd is below {threshold:.1%}; null when unavailable."}
    dictionary["negative_return_90d"]={"role":"target","description":f"1 when return_90cd is below {threshold:.1%}; null when unavailable."}
    if output_path:
        out=Path(output_path); out.parent.mkdir(parents=True,exist_ok=True); dataset.to_parquet(out,index=False)
        (out.parent/"ml_data_dictionary.json").write_text(json.dumps(dictionary,indent=2),encoding="utf-8")
        (out.parent/"ml_feature_schema.json").write_text(json.dumps(all_features,indent=2),encoding="utf-8")
        manifest_path=root/"manifest.json"
        manifest=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"dataset_name":"unknown","synthetic":True}
        (out.parent/"ml_dataset_metadata.json").write_text(json.dumps({"synthetic":True,"source_manifest":manifest,"negative_return_threshold":threshold,"event_count":len(dataset),"feature_asof_convention":"strictly before filing date","calendar_target_convention":"first observed close on/after filing date plus horizon calendar days"},indent=2,default=_json_default),encoding="utf-8")
    return dataset,dictionary

def _feature_description(name):
    descriptions={"filing_type":"Filing form, available at filing publication.","sector":"Company sector metadata.","number_of_changed_paragraphs":"Number of paragraph comparisons for this filing.","number_of_added_risks":"Diff rows labeled added/new.","number_of_modified_risks":"Diff rows labeled modified.","number_of_removed_risks":"Diff rows labeled removed.","number_of_unique_risk_categories":"Distinct categories in this filing's risk records.","mean_severity_score":"Mean filing risk severity.","maximum_severity_score":"Maximum filing risk severity.","mean_novelty_score":"Mean filing risk novelty.","mean_confidence_score":"Mean risk record confidence.","weighted_risk_change_score":"0-100 proxy: 60% mean severity and 40% mean novelty; not a predicted probability.","previous_5_session_return":"Adjusted close return over five completed sessions ending strictly before filing date.","previous_20_session_return":"Adjusted close return over twenty completed sessions ending strictly before filing date.","previous_20_session_volatility":"Sample standard deviation of recent daily returns through the last pre-filing close.","previous_20_session_mean_volume":"Mean daily volume for up to 20 sessions ending before filing date.","previous_20_session_volume_std":"Sample standard deviation of volume for up to 20 sessions ending before filing date."}
    if name.startswith("risk_category_"): return f"Count of risk records in category {name.removeprefix('risk_category_')} for this filing."
    return descriptions.get(name,"Filing-event input computed from source data available at or before filing time.")

def _target_description(name,threshold):
    if name.startswith("negative_return_"): return f"Binary outcome: return below {threshold:.1%}; never an input feature."
    if name.startswith("maximum_drawdown"): return "Maximum peak-to-trough drawdown from pre-filing baseline through target horizon."
    if name=="return_1d": return "Return from last pre-filing close to first trading close strictly after filing date."
    if name=="return_5td": return "Return from last pre-filing close through fifth trading close strictly after filing date."
    return "Adjusted-close return from last pre-filing close to first trading close on/after filing date plus the stated calendar days."

def chronological_split(data:pd.DataFrame,target:str,purge_days=30):
    valid=data.dropna(subset=[target,"filing_date"]).copy().sort_values("filing_date")
    valid["filing_date"]=pd.to_datetime(valid.filing_date)
    dates=sorted(valid.filing_date.unique())
    if len(dates)<5: return {"train":valid.iloc[:0],"validation":valid.iloc[:0],"test":valid,"boundaries":{},"warning":"Too few distinct filing dates for chronological split."}
    val_start=pd.Timestamp(dates[max(1,int(len(dates)*.60))]); test_start=pd.Timestamp(dates[max(2,int(len(dates)*.80))])
    train_cutoff=val_start-pd.Timedelta(days=purge_days); val_cutoff=test_start-pd.Timedelta(days=purge_days)
    train=valid[valid.filing_date<train_cutoff]; validation=valid[(valid.filing_date>=val_start)&(valid.filing_date<val_cutoff)]; test=valid[valid.filing_date>=test_start]
    warning=None
    if min(len(train),len(validation),len(test))<2:
        warning=f"Purged chronological split is small (train={len(train)}, validation={len(validation)}, test={len(test)}); no random fallback used."
    return {"train":train,"validation":validation,"test":test,"boundaries":{"validation_start":val_start.date().isoformat(),"test_start":test_start.date().isoformat(),"train_cutoff":train_cutoff.date().isoformat(),"validation_cutoff":val_cutoff.date().isoformat()},"warning":warning}

def _make_estimators(seed=42):
    return {"dummy":DummyClassifier(strategy="prior"),"logistic_regression":LogisticRegression(max_iter=2000,class_weight="balanced",random_state=seed),
      "random_forest":RandomForestClassifier(n_estimators=200,min_samples_leaf=2,class_weight="balanced_subsample",random_state=seed,n_jobs=1),
      "gradient_boosting":GradientBoostingClassifier(random_state=seed,n_estimators=80,max_depth=1,learning_rate=.05)}

def _pipeline(estimator,numeric,categorical):
    transform=ColumnTransformer([("numeric",Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),numeric),
      ("categorical",Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore"))]),categorical)],remainder="drop")
    return Pipeline([("preprocess",transform),("model",estimator)])

def _metrics(y_true,y_prob,threshold=.5):
    y_true=np.asarray(y_true,dtype=int); y_pred=(np.asarray(y_prob)>=threshold).astype(int); unique=np.unique(y_true)
    return {"n":int(len(y_true)),"class_distribution":{str(int(k)):int(v) for k,v in zip(*np.unique(y_true,return_counts=True))},
      "accuracy":float(accuracy_score(y_true,y_pred)),"precision":float(precision_score(y_true,y_pred,zero_division=0)),"recall":float(recall_score(y_true,y_pred,zero_division=0)),"f1":float(f1_score(y_true,y_pred,zero_division=0)),
      "roc_auc":float(roc_auc_score(y_true,y_prob)) if len(unique)==2 else None,"pr_auc":float(average_precision_score(y_true,y_prob)) if len(unique)==2 else None,
      "brier_score":float(brier_score_loss(y_true,y_prob)),"confusion_matrix":confusion_matrix(y_true,y_pred,labels=[0,1]).tolist(),
      "interpretation":{"accuracy":"Fraction classified correctly; compare with majority-class accuracy.","precision":"Share of predicted negative-return events that were negative-return events.","recall":"Share of actual negative-return events detected.","f1":"Harmonic mean of precision and recall.","roc_auc":"Ranking discrimination across thresholds; undefined for a single-class test set.","pr_auc":"Average precision for the positive class; undefined for a single-class test set.","brier_score":"Mean squared probability error; lower is better but small test sets make it unstable.","confusion_matrix":"Rows are actual classes 0/1; columns are predicted classes 0/1."}}

def _feature_effects(pipe):
    try: names=pipe.named_steps["preprocess"].get_feature_names_out(); model=pipe.named_steps["model"]
    except Exception:return []
    if hasattr(model,"coef_"): values=np.ravel(model.coef_)
    elif hasattr(model,"feature_importances_"): values=model.feature_importances_
    else:return []
    order=np.argsort(np.abs(values))[::-1][:15]
    return [{"feature":str(names[i]),"effect":float(values[i])} for i in order]

def train_evaluate(dataset:pd.DataFrame,output_dir:Path|str,targets=None,seed=42,purge_days=None,negative_return_threshold=-.05):
    out=Path(output_dir); models_dir=out/"models"; eval_dir=out/"evaluation"; plots_dir=out/"plots"
    for d in (models_dir,eval_dir,plots_dir): d.mkdir(parents=True,exist_ok=True)
    targets=targets or ["negative_return_30d","negative_return_60d","negative_return_90d"]
    feature_cols=[c for c in FIXED_FEATURES+[x for x in dataset.columns if x.startswith("risk_category_")] if c in dataset]
    categorical=[c for c in ["filing_type","sector"] if c in feature_cols]; numeric=[c for c in feature_cols if c not in categorical]
    results={}; metadata={"dataset_version":"1.0.0","synthetic":True,"warning":SYNTHETIC_WARNING,"random_seed":seed,"trained_at":datetime.now(timezone.utc).isoformat(),"features":feature_cols,"targets":{}}
    for target in targets:
        if target not in dataset: continue
        horizon_days=int(target.removeprefix("negative_return_").removesuffix("d")); purge_days=purge_days or horizon_days
        split=chronological_split(dataset,target,purge_days); train,valid,test=split["train"],split["validation"],split["test"]
        ytrain=train[target].astype(int) if len(train) else pd.Series(dtype=int)
        all_classes=sorted(pd.to_numeric(dataset[target],errors="coerce").dropna().astype(int).unique().tolist())
        entry={"target":target,"class_distribution":dataset[target].value_counts(dropna=True).sort_index().to_dict(),"split_sizes":{"train":len(train),"validation":len(valid),"test":len(test)},"split_boundaries":split["boundaries"],"split_warning":split["warning"],"models":{},"trained_model_names":[]}
        if len(train)<4 or len(np.unique(ytrain))<2:
            entry["status"]="not_trainable_single_class_or_too_few_training_rows"; entry["warning"]="Training data has fewer than four rows or does not contain both outcome classes."
            results[target]=entry; metadata["targets"][target]=entry; continue
        model_results=[]; fitted={}
        for model_name,estimator in _make_estimators(seed).items():
            pipe=_pipeline(estimator,numeric,categorical)
            pipe.fit(train[feature_cols],ytrain)
            fitted[model_name]=pipe; entry["trained_model_names"].append(model_name)
            validation_metrics=None
            if len(valid):
                p=pipe.predict_proba(valid[feature_cols])[:,1]
                validation_metrics=_metrics(valid[target].astype(int),p)
            test_metrics=None
            if len(test):
                ptest=pipe.predict_proba(test[feature_cols])[:,1]
                test_metrics=_metrics(test[target].astype(int),ptest)
            entry["models"][model_name]={"validation":validation_metrics,"test":test_metrics,"feature_effects":_feature_effects(pipe)}
            model_results.append((model_name,validation_metrics))
        def rank(item):
            _,m=item
            if not m:return (-1,-1)
            return (m["pr_auc"] if m["pr_auc"] is not None else m["accuracy"],m["accuracy"])
        selected=max(model_results,key=rank)[0]
        chosen=fitted[selected]; test_metrics=entry["models"][selected]["test"]
        # Require a minimally sized, two-class held-out set before enabling probabilities.
        eval_valid=bool(test_metrics and test_metrics["n"]>=10 and len(test_metrics["class_distribution"])==2)
        entry.update({"status":"evaluated" if eval_valid else "insufficient_held_out_evaluation","selected_model":selected,"test_evaluation_sufficient":eval_valid,
            "test_limitation":None if eval_valid else "Held-out test needs at least 10 events and both classes; probabilities are suppressed."})
        if test_metrics and test_metrics["n"]:
            counts=test_metrics["class_distribution"]; majority=max(counts.values())/test_metrics["n"]
            entry["majority_class_test_accuracy"]=float(majority)
        target_artifact=models_dir/f"{selected}_{target}.joblib"
        model_artifacts={}
        for model_name,model_pipe in fitted.items():
            artifact=models_dir/f"{model_name}_{target}.joblib"; joblib.dump(model_pipe,artifact); model_artifacts[model_name]=artifact.name
        metadata["targets"][target]={**entry,"selected_artifact":target_artifact.name,"model_artifacts":model_artifacts,"feature_names":feature_cols,"target_definition":f"1 if associated future return < {negative_return_threshold:.1%}; target value={target}","negative_return_threshold":negative_return_threshold,"training_period":[str(train.filing_date.min().date()) if len(train) else None,str(train.filing_date.max().date()) if len(train) else None],"validation_period":[str(valid.filing_date.min().date()) if len(valid) else None,str(valid.filing_date.max().date()) if len(valid) else None],"test_period":[str(test.filing_date.min().date()) if len(test) else None,str(test.filing_date.max().date()) if len(test) else None]}
        _save_plots(target,entry,chosen,test,feature_cols,plots_dir)
        results[target]=entry
    (eval_dir/"metrics.json").write_text(json.dumps(results,indent=2,default=_json_default),encoding="utf-8")
    (models_dir/"model_metadata.json").write_text(json.dumps(metadata,indent=2,default=_json_default),encoding="utf-8")
    return results,metadata

def _json_default(x):
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.floating,)):return None if not np.isfinite(x) else float(x)
    if isinstance(x,(np.ndarray,)):return x.tolist()
    if pd.isna(x):return None
    if hasattr(x,"isoformat"):return x.isoformat()
    return str(x)

def _save_plots(target,entry,pipe,test,feature_cols,out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    models=entry.get("models",{})
    # Model comparison: test accuracy and PR-AUC, undefined values remain absent.
    names=list(models); fig,ax=plt.subplots(figsize=(9,4)); width=.38; xs=np.arange(len(names))
    accuracy=[models[n]["test"]["accuracy"] if models[n]["test"] else np.nan for n in names]
    pr_auc=[models[n]["test"]["pr_auc"] if models[n]["test"] and models[n]["test"]["pr_auc"] is not None else np.nan for n in names]
    ax.bar(xs-width/2,accuracy,width,label="Accuracy",color="#527da8"); ax.bar(xs+width/2,pr_auc,width,label="PR-AUC",color="#d28b42")
    ax.set_xticks(xs,labels=names,rotation=20); ax.set_ylim(0,1); ax.set_ylabel("Held-out metric"); ax.legend(); ax.set_title(f"{target}: chronological test metrics · synthetic")
    fig.tight_layout(); fig.savefig(out/f"model_comparison_{target}.png",dpi=140); plt.close(fig)
    effects=entry.get("models",{}).get(entry.get("selected_model"),{}).get("feature_effects",[])
    if effects:
        ef=pd.DataFrame(effects).sort_values("effect"); fig,ax=plt.subplots(figsize=(8,5)); ax.barh(ef.feature,ef.effect,color="#3a9b87"); ax.set_title(f"{entry.get('selected_model')} feature effects · not causal"); fig.tight_layout(); fig.savefig(out/f"feature_effects_{target}.png",dpi=140); plt.close(fig)
    if len(test) and entry.get("selected_model"):
        y=entry["models"][entry["selected_model"]]["test"]
        if y:
            cm=np.asarray(y["confusion_matrix"]); fig,ax=plt.subplots(figsize=(4,4)); ax.imshow(cm,cmap="Blues"); ax.set_xticks([0,1],labels=["pred 0","pred 1"]); ax.set_yticks([0,1],labels=["true 0","true 1"])
            for (i,j),v in np.ndenumerate(cm): ax.text(j,i,str(v),ha="center",va="center")
            ax.set_title(f"{target} confusion matrix · synthetic"); fig.tight_layout(); fig.savefig(out/f"confusion_{target}.png",dpi=140); plt.close(fig)
            probs=pipe.predict_proba(test[feature_cols])[:,1]
            fig,ax=plt.subplots(figsize=(7,4)); ax.hist(probs,bins=np.linspace(0,1,11),color="#735b9c",edgecolor="white"); ax.set_xlim(0,1); ax.set_xlabel("Predicted probability"); ax.set_ylabel("Test observations"); ax.set_title(f"{target}: held-out probabilities · synthetic"); fig.tight_layout(); fig.savefig(out/f"probability_distribution_{target}.png",dpi=140); plt.close(fig)

def run_training_workflow(data_dir:Path|str="data/gold",artifacts_dir:Path|str="artifacts",processed_path:Path|str="data/processed/ml_training_dataset.parquet",threshold=-.05):
    dataset,dictionary=build_ml_dataset(data_dir,processed_path,threshold)
    out=Path(artifacts_dir); results,metadata=train_evaluate(dataset,out,negative_return_threshold=threshold)
    return dataset,dictionary,results,metadata

def predict_filing_risk(ticker,accession_number,prediction_horizon="30d",data_dir="data/gold",artifacts_dir="artifacts",model_name=None):
    target=HORIZONS.get(prediction_horizon,(None,None))[0]
    response={"ticker":ticker,"accession_number":accession_number,"prediction_horizon":prediction_horizon,"status":"unavailable","predicted_probability":None,"warnings":[SYNTHETIC_WARNING]}
    if target is None: response["status"]="unsupported_horizon"; return response
    data_path=Path(data_dir).parent/"processed/ml_training_dataset.parquet"
    if not data_path.exists(): response["status"]="training_dataset_missing"; return response
    ds=pd.read_parquet(data_path); row=ds[(ds.ticker.astype(str)==str(ticker))&(ds.accession_number.astype(str)==str(accession_number))]
    if row.empty: response["status"]="filing_not_found"; return response
    meta_path=Path(artifacts_dir)/"models/model_metadata.json"
    if not meta_path.exists(): response["status"]="model_not_trained"; return response
    metadata=json.loads(meta_path.read_text(encoding="utf-8")); target_meta=metadata.get("targets",{}).get(target)
    if not target_meta: response["status"]="model_not_trained_for_horizon"; return response
    model_name=model_name or target_meta.get("selected_model")
    model_entry=target_meta.get("models",{}).get(model_name,{})
    response["model_metadata"]={"model":model_name,"model_version":metadata.get("trained_at"),"negative_return_threshold":target_meta.get("negative_return_threshold"),"status":target_meta.get("status"),"test_limitation":target_meta.get("test_limitation"),"test_metrics":model_entry.get("test")}
    response["risk_change_score"]=row.iloc[0].get("weighted_risk_change_score")
    expected=target_meta.get("feature_names",[])
    missing=[c for c in expected if c not in row or pd.isna(row.iloc[0].get(c))]
    response["data_quality_warnings"]=[f"Missing model input features will use training-fitted imputation: {', '.join(missing)}"] if missing else []
    if not row.iloc[0].get("base_trade_date"): response["data_quality_warnings"].append("No historical pre-filing market baseline is available.")
    if model_name not in target_meta.get("model_artifacts",{}): response["status"]="model_not_trained"; return response
    if not target_meta.get("test_evaluation_sufficient"):
        response["status"]="model_not_adequately_evaluated"; response["warnings"].append(target_meta.get("test_limitation")); return response
    artifact=Path(artifacts_dir)/"models"/target_meta["model_artifacts"][model_name]
    pipe=joblib.load(artifact)
    if list(pipe.feature_names_in_)!=expected or any(c not in row for c in expected): response["status"]="feature_schema_mismatch"; return response
    response["predicted_probability"]=float(pipe.predict_proba(row[expected])[:,1][0]); response["status"]="available_with_missing_features" if missing else "available"
    response["main_contributing_features"]=model_entry.get("feature_effects",[])[:5]
    return response

def train_spark_mllib(dataset_path="data/processed/ml_training_dataset.parquet",output_dir="artifacts/models/spark",target="negative_return_30d",spark=None):
    """Optional chronological Spark MLlib path. Returns status instead of fabricating a model."""
    try:
        from pyspark.sql import SparkSession, functions as F
        from pyspark.ml import Pipeline
        from pyspark.ml.feature import Imputer, StringIndexer, OneHotEncoder, VectorAssembler
        from pyspark.ml.classification import LogisticRegression, RandomForestClassifier, GBTClassifier
        from pyspark.ml.evaluation import BinaryClassificationEvaluator
    except ImportError as exc: raise RuntimeError("Install pyspark with `python -m pip install -e '.[spark]'` for Spark MLlib training") from exc
    spark=spark or SparkSession.builder.appName("SecuLenseMLlib").getOrCreate()
    df=spark.read.parquet(str(dataset_path)).withColumn("filing_date",F.to_date("filing_date")).filter(F.col(target).isNotNull()).orderBy("filing_date")
    n=df.count()
    if n<10:return {"status":"insufficient_rows","rows":n,"warning":SYNTHETIC_WARNING}
    ordered=df.select("filing_date").collect(); val_start=ordered[int(n*.6)][0]; test_start=ordered[int(n*.8)][0]; days=int(target.split("_")[-1][:-1])
    train=df.filter(F.col("filing_date")<F.date_sub(F.lit(val_start),days)); val=df.filter((F.col("filing_date")>=F.lit(val_start))&(F.col("filing_date")<F.date_sub(F.lit(test_start),days))); test=df.filter(F.col("filing_date")>=F.lit(test_start))
    if train.select(target).distinct().count()<2:return {"status":"not_trainable_single_class","rows":n,"warning":SYNTHETIC_WARNING}
    features=[c for c in FIXED_FEATURES if c in df.columns]+[c for c in df.columns if c.startswith("risk_category_")]
    cats=[c for c in ("filing_type","sector") if c in features]; nums=[c for c in features if c not in cats]
    stages=[]; num_out=nums
    if nums:
        imputed=[f"{c}_imputed" for c in nums]; stages.append(Imputer(inputCols=nums,outputCols=imputed,strategy="median")); num_out=imputed
    idx=[f"{c}_idx" for c in cats]; hot=[f"{c}_oh" for c in cats]
    for c,o in zip(cats,idx): stages.append(StringIndexer(inputCol=c,outputCol=o,handleInvalid="keep"))
    if cats: stages.append(OneHotEncoder(inputCols=idx,outputCols=hot,handleInvalid="keep"))
    stages.append(VectorAssembler(inputCols=num_out+hot,outputCol="features",handleInvalid="keep"))
    models={"logistic_regression":LogisticRegression(labelCol=target,featuresCol="features",maxIter=100),"random_forest":RandomForestClassifier(labelCol=target,featuresCol="features",numTrees=100,seed=42),"gradient_boosting":GBTClassifier(labelCol=target,featuresCol="features",maxIter=60,seed=42)}
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); scores={}
    evaluator=BinaryClassificationEvaluator(labelCol=target,rawPredictionCol="rawPrediction",metricName="areaUnderROC")
    for name,model in models.items():
        pipeline=Pipeline(stages=stages+[model]); fitted=pipeline.fit(train); validation=fitted.transform(val); test_pred=fitted.transform(test)
        scores[name]={"validation_roc_auc":evaluator.evaluate(validation) if val.count() and val.select(target).distinct().count()==2 else None,"test_roc_auc":evaluator.evaluate(test_pred) if test.count() and test.select(target).distinct().count()==2 else None,"test_rows":test.count()}
        fitted.write().overwrite().save(str(out/f"{name}_{target}"))
    result={"status":"trained_spark_mllib","target":target,"split_rows":{"train":train.count(),"validation":val.count(),"test":test.count()},"models":scores,"warning":SYNTHETIC_WARNING}
    (out/"spark_metrics.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
