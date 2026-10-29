import unittest

from secu_lense.server.app import (
    app,
    health,
    auth_status,
    get_model_metadata,
    get_data_quality_report,
    ask_copilot,
    CopilotRequest,
    load_all_datasets,
    get_fundamentals,
    get_comparisons,
    get_alerts,
    get_freshness,
    get_watchlist,
    toggle_watchlist,
    WatchlistToggleRequest,
    refresh_lakehouse,
    lakehouse_status,
)


class TestSecuLenseFastAPI(unittest.TestCase):
    def test_health_endpoint(self):
        res = health()
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["app"], "SecuLense")
        self.assertEqual(res["stack"], "React + FastAPI (Python)")
        self.assertEqual(res["version"], "0.1.0")

    def test_auth_status_endpoint(self):
        res = auth_status()
        self.assertIn("setup_required", res)
        self.assertIsInstance(res["setup_required"], bool)

    def test_datasets_loader(self):
        data = load_all_datasets()
        self.assertIn("companies", data)
        self.assertIn("filings", data)
        self.assertIn("risk_scores", data)
        self.assertIn("event_returns", data)
        self.assertIn("fundamentals", data)
        self.assertIn("company_comparisons", data)
        self.assertIn("watchlist_alerts", data)
        self.assertIn("financial_glossary", data)
        self.assertIn("educational_qa", data)

    def test_model_metadata_endpoint(self):
        res = get_model_metadata({"id": 1, "username": "test"})
        self.assertTrue(res.get("available"))
        self.assertIn("targets", res)

    def test_quality_report_endpoint(self):
        res = get_data_quality_report({"id": 1, "username": "test"})
        self.assertIn("table_stats", res)
        self.assertGreaterEqual(len(res["table_stats"]), 8)

    def test_fundamentals_endpoint(self):
        res = get_fundamentals(ticker="AAPL", _={"id": 1, "username": "test"})
        self.assertIn("records", res)
        self.assertGreater(res["count"], 0)
        first = res["records"][0]
        self.assertEqual(first["ticker"], "AAPL")
        self.assertIn("revenue_billions", first)
        self.assertIn("gross_margin_pct", first)

    def test_comparisons_endpoint(self):
        res = get_comparisons({"id": 1, "username": "test"})
        self.assertIn("comparisons", res)
        self.assertGreaterEqual(res["count"], 5)

    def test_alerts_endpoint(self):
        res = get_alerts(_={"id": 1, "username": "test"})
        self.assertIn("alerts", res)
        self.assertGreater(res["count"], 0)

    def test_freshness_endpoint(self):
        res = get_freshness({"id": 1, "username": "test"})
        self.assertIn("data_freshness", res)

    def test_watchlist_endpoints(self):
        user = {"id": 999, "username": "test"}
        res = get_watchlist(user)
        self.assertIn("watchlist", res)
        self.assertIn("AAPL", res["watchlist"])

        toggle_res = toggle_watchlist(WatchlistToggleRequest(ticker="TSLA", action="remove"), user)
        self.assertTrue(toggle_res["ok"])
        self.assertNotIn("TSLA", toggle_res["watchlist"])

    def test_copilot_glossary_lookup(self):
        req = CopilotRequest(question="What is gross margin?")
        res = ask_copilot(req, {"id": 1, "username": "test"})
        self.assertEqual(res["category"], "glossary")
        self.assertIn("Gross margin", res["answer"])

    def test_copilot_returns_lookup(self):
        req = CopilotRequest(question="What were the event returns for AAPL?")
        res = ask_copilot(req, {"id": 1, "username": "test"})
        self.assertEqual(res["category"], "events")
        self.assertIn("event returns", res["answer"].lower())

    def test_copilot_diffs_lookup(self):
        req = CopilotRequest(question="What changed in the filings?")
        res = ask_copilot(req, {"id": 1, "username": "test"})
        self.assertEqual(res["category"], "diffs")
        self.assertIn("paragraph changes", res["answer"].lower())

    def test_spark_status_endpoint(self):
        from secu_lense.server.app import spark_status
        res = spark_status({"id": 1, "username": "test"})
        self.assertIn("available", res)
        self.assertIn("engine", res)
        self.assertIn("registered_views", res)


    def test_lakehouse_endpoints(self):
        user = {"id": 1, "username": "test"}
        status_res = lakehouse_status(user)
        self.assertIn("engine", status_res)
        self.assertIn("registered_views", status_res)

        refresh_res = refresh_lakehouse(user)
        self.assertEqual(refresh_res["message"], "Medallion Lakehouse pipeline executed successfully")
        self.assertEqual(refresh_res["result"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
