import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from secu_lense.ml_pipeline import predict_filing_risk

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--ticker",required=True); p.add_argument("--accession",required=True); p.add_argument("--horizon",choices=["30d","60d","90d"],default="30d"); a=p.parse_args()
    print(json.dumps(predict_filing_risk(a.ticker,a.accession,a.horizon),indent=2))
