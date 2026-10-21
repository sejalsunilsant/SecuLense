import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--metrics",default="artifacts/evaluation/metrics.json"); a=p.parse_args()
    path=Path(a.metrics)
    if not path.exists(): raise SystemExit("No evaluation file found. Run scripts/03_train_models.py first.")
    data=json.loads(path.read_text(encoding="utf-8"))
    print("SYNTHETIC ONLY · chronological held-out metrics; no predictive validity implied")
    for target,result in data.items():
        print(f"{target}: status={result.get('status')} sizes={result.get('split_sizes')} selected={result.get('selected_model')}")
        model=result.get("selected_model"); metrics=result.get("models",{}).get(model,{}).get("test") if model else None
        print("  test:",json.dumps(metrics,sort_keys=True))
