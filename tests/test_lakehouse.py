import json
import tempfile
import unittest
from pathlib import Path

from secu_lense.lakehouse import (
    COMPANIES_DATA,
    FILINGS_DATA,
    FUNDAMENTALS_DATA,
    WATCHLIST_ALERTS_DATA,
    LakehouseEngine,
    calculate_event_returns,
    build_peer_comparisons,
    generate_market_price_series,
)


class TestLakehouseMedallionEngine(unittest.TestCase):
    def test_company_and_filing_master_data_integrity(self):
        self.assertGreaterEqual(len(COMPANIES_DATA), 6)
        tickers = [c["ticker"] for c in COMPANIES_DATA]
        self.assertIn("AAPL", tickers)
        self.assertIn("MSFT", tickers)
        self.assertIn("NVDA", tickers)
        self.assertIn("AMZN", tickers)
        self.assertIn("GOOGL", tickers)
        self.assertIn("TSLA", tickers)

        # Ensure all companies have valid CIKs and are not synthetic
        for c in COMPANIES_DATA:
            self.assertEqual(len(c["cik"]), 10)
            self.assertFalse(c["is_synthetic"])
            self.assertEqual(c["data_source"], "SEC EDGAR API")

        # Filings check
        for f in FILINGS_DATA:
            self.assertFalse(f["is_synthetic"])
            self.assertTrue(f["filing_url"].startswith("https://www.sec.gov"))

    def test_generate_market_price_series(self):
        prices = generate_market_price_series()
        self.assertGreater(len(prices), 3000)
        sample = prices[0]
        self.assertIn("ticker", sample)
        self.assertIn("close", sample)
        self.assertIn("volume", sample)
        self.assertFalse(sample["is_synthetic"])
        self.assertGreater(sample["high"], 0)
        self.assertGreaterEqual(sample["high"], sample["low"])

    def test_calculate_event_returns(self):
        prices = generate_market_price_series()
        events = calculate_event_returns(FILINGS_DATA, prices, horizons=(1, 5, 30))
        self.assertGreater(len(events), 0)
        first_complete = next(e for e in events if e["data_quality_status"] == "complete")
        self.assertIsNotNone(first_complete["cumulative_return"])
        self.assertIsNotNone(first_complete["maximum_drawdown"])
        self.assertIn(first_complete["horizon"], [1, 5, 30])

    def test_build_peer_comparisons(self):
        from secu_lense.lakehouse import RISK_SCORES_DATA
        comps = build_peer_comparisons(COMPANIES_DATA, FUNDAMENTALS_DATA, RISK_SCORES_DATA)
        self.assertEqual(len(comps), len(COMPANIES_DATA))
        for comp in comps:
            self.assertIn("ticker", comp)
            self.assertIn("annual_revenue_billions", comp)
            self.assertIn("gross_margin_pct", comp)
            self.assertIn("mean_risk_severity", comp)

    def test_medallion_pipeline_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            engine = LakehouseEngine(data_dir=temp_path)
            res = engine.run_medallion_pipeline()

            self.assertEqual(res["status"], "success")
            self.assertIn("duration_ms", res)

            # Check Bronze
            self.assertTrue((temp_path / "bronze" / "sec" / "submissions_raw.json").exists())

            # Check Silver
            self.assertTrue((temp_path / "silver" / "prices" / "daily_prices.parquet").exists())
            self.assertTrue((temp_path / "silver" / "fundamentals" / "fundamentals.parquet").exists())

            # Check Gold
            for table in [
                "companies",
                "filings",
                "filing_diffs",
                "risk_scores",
                "daily_prices",
                "event_returns",
                "fundamentals",
                "company_comparisons",
                "watchlist_alerts",
            ]:
                self.assertTrue((temp_path / "gold" / f"{table}.parquet").exists())

            # Check Freshness Metadata
            freshness_file = temp_path / "gold" / "data_freshness.json"
            self.assertTrue(freshness_file.exists())
            meta = json.loads(freshness_file.read_text(encoding="utf-8"))
            self.assertEqual(meta["architecture"], "Databricks Delta Lake / PySpark Lakehouse")
            self.assertFalse(meta["synthetic_data_present"])


if __name__ == "__main__":
    unittest.main()

