import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from secu_lense.eda import explore

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--data-dir",default="data/gold"); p.add_argument("--output-dir",default="artifacts/eda"); a=p.parse_args()
    report=explore(a.data_dir,a.output_dir)
    print(f"Synthetic EDA complete: {report['companies']} companies, {report['filings']} filings; see {a.output_dir}")
