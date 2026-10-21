# SecuLense Demo Dataset

**Important:** This bundle is for software development and testing. Filing text, risk scores, and OHLCV prices are synthetic. Company names, tickers, and CIK values are reference metadata only; the generated filing identifiers are synthetic and do not represent actual SEC filings. Do not use this dataset for investment decisions or claim it represents real historical stock performance.

## Contents
- `companies.csv` — sample company reference metadata.
- `filings.csv` — filing metadata for synthetic filing records.
- `raw_filings/` — JSON examples with synthetic Item 1A and Item 7 content.
- `filing_diffs.csv` — example added/modified/removed paragraph comparisons.
- `risk_scores.csv` — synthetic risk labels/scores for UI and pipeline testing.
- `prices/daily_prices.csv` — synthetic weekday OHLCV observations, 2023–2025.
- `glossary/financial_glossary.csv` — beginner financial definitions.
- `glossary/educational_qa.json` — seed questions for learning copilot.

## Suggested use
1. Load CSV files with pandas or Spark.
2. Use `raw_filings/*.json` to test section extraction and source-aware UI.
3. Use `filing_diffs.csv` to test the filing comparison view.
4. Use `prices/daily_prices.csv` to test temporal joins and return calculations.
5. Replace synthetic records with verified SEC and licensed market data before drawing any empirical conclusions.

## Limitations
- Dates are plausible demonstration dates, not a guarantee of exact real filing dates.
- Prices are generated randomly and are not actual prices.
- Synthetic risk scores are randomly generated and are not LLM outputs.
- The synthetic market series is not intentionally calibrated to match filings.
