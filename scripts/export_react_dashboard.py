"""Export the locally loaded Parquet demo tables for the React dashboard."""
from pathlib import Path
import json

from secu_lense import config
from secu_lense.sources import read_table


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "private" / "dashboard.json"
TABLES = (
    "companies", "filings", "filing_diffs", "risk_scores", "daily_prices",
    "event_returns", "financial_glossary", "educational_qa",
)


def main() -> None:
    payload = {}
    for name in TABLES:
        path = config.DATA_DIR / "gold" / f"{name}.parquet"
        if path.exists():
            frame = read_table(path)
            payload[name] = json.loads(frame.to_json(orient="records", date_format="iso"))
        else:
            payload[name] = []
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"Exported local dashboard data to {OUTPUT}")


if __name__ == "__main__":
    main()
