import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from secu_lense.ml_pipeline import build_ml_dataset

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--data-dir",default="data/gold"); p.add_argument("--output",default="data/processed/ml_training_dataset.parquet"); p.add_argument("--threshold",type=float,default=-.05); a=p.parse_args()
    ds,_=build_ml_dataset(a.data_dir,a.output,a.threshold)
    print(f"Built {len(ds)} filing events; target rows by horizon: "+", ".join(f"{c}={int(ds[c].notna().sum())}" for c in ("negative_return_30d","negative_return_60d","negative_return_90d")))
