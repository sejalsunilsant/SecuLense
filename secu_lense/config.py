from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
WATCHLIST = [x.strip().upper() for x in os.getenv("WATCHLIST", "AAPL,MSFT,NVDA,AMZN,TSLA").split(",") if x.strip()]
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "SecuLense research contact@example.com")
MARKET_DATA_PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "yfinance")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deterministic")
PREDICTION_HORIZON = int(os.getenv("PREDICTION_HORIZON", "30"))
NEGATIVE_RETURN_THRESHOLD = float(os.getenv("NEGATIVE_RETURN_THRESHOLD", "-0.05"))

def ensure_dirs():
    for part in ("bronze/sec", "bronze/market", "silver/filings", "silver/prices", "gold/risk_features", "gold/event_returns", "models"):
        (DATA_DIR / part).mkdir(parents=True, exist_ok=True)
