import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from secu_lense.ml_pipeline import train_evaluate

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--dataset",default="data/processed/ml_training_dataset.parquet"); p.add_argument("--artifacts",default="artifacts"); a=p.parse_args()
    dataset=pd.read_parquet(a.dataset)
    metadata_path=Path(a.dataset).parent/"ml_dataset_metadata.json"
    threshold=json.loads(metadata_path.read_text(encoding="utf-8")).get("negative_return_threshold",-.05) if metadata_path.exists() else -.05
    result,_=train_evaluate(dataset,a.artifacts,negative_return_threshold=threshold)
    print("Training complete (synthetic demonstration). Targets: "+", ".join(result))
