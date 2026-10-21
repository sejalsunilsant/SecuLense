import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from secu_lense.eda import explore
from secu_lense.ml_pipeline import run_training_workflow

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--data-dir",default="data/gold"); p.add_argument("--artifacts-dir",default="artifacts"); p.add_argument("--processed",default="data/processed/ml_training_dataset.parquet"); p.add_argument("--threshold",type=float,default=-.05); a=p.parse_args()
    explore(a.data_dir,"artifacts/eda")
    ds,dictionary,metrics,metadata=run_training_workflow(a.data_dir,a.artifacts_dir,a.processed,a.threshold)
    print(f"Pipeline done on {len(ds)} synthetic filing events. EDA=artifacts/eda; models={a.artifacts_dir}/models; evaluation={a.artifacts_dir}/evaluation; plots={a.artifacts_dir}/plots")
    for target,report in metrics.items(): print(f"{target}: {report.get('status')} classes={report.get('class_distribution')} model={report.get('selected_model')}")
