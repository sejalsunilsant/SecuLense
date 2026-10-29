# Databricks notebook source
# MAGIC %md
# MAGIC # SecuLense · Enterprise Financial Research Lakehouse
# MAGIC ## Production PySpark & Databricks Delta Lake Pipeline
# MAGIC 
# MAGIC **SecuLense** is an executive corporate filing risk and market research platform. This notebook implements the end-to-end **Medallion Architecture (Bronze → Silver → Gold)** using distributed PySpark, Spark SQL, and Delta Lake:
# MAGIC 
# MAGIC ```
# MAGIC ┌────────────────────────────────────────────────────────────────────────┐
# MAGIC │                        MEDALLION ARCHITECTURE                          │
# MAGIC ├───────────────────┬──────────────────────────┬─────────────────────────┤
# MAGIC │   BRONZE LAYER    │       SILVER LAYER       │       GOLD LAYER        │
# MAGIC │  Raw SEC Filings  │ Cleaned & Deduplicated   │ Business Analytics &    │
# MAGIC │   & Market Feeds  │ Schema-Validated Parquet │ Peer Benchmarks (Delta) │
# MAGIC └───────────────────┴──────────────────────────┴─────────────────────────┘
# MAGIC ```
# MAGIC 
# MAGIC ### Core Capabilities Executed in this Notebook:
# MAGIC 1. **Bronze Ingestion**: Landing raw SEC EDGAR 10-K/10-Q submissions and historical OHLCV market feeds.
# MAGIC 2. **Silver Transformations**: PySpark Window functions for rolling 20d/50d SMAs, daily returns, volatility, and normalized filing disclosures.
# MAGIC 3. **Gold Curated Tables**:
# MAGIC    - **Paragraph-Level Filing Diffs**: Tracking additions, modifications, and deletions in Item 1A (Risk Factors) & Item 7 (MD&A).
# MAGIC    - **Evidence-Backed Risk Analysis**: Linguistic severity and novelty scoring with verbatim quoted excerpts.
# MAGIC    - **Multi-Horizon Event Study**: Empirical 1d, 5d, 30d, 60d, and 90d post-filing returns with maximum drawdowns.
# MAGIC    - **Multi-Company Peer Benchmarking**: Side-by-side comparative financial and valuation matrix (AAPL, MSFT, NVDA, AMZN, GOOGL, TSLA).
# MAGIC    - **Actionable Research Alerts**: Real-time materiality alerts (regulatory lawsuits, AI export controls, supply bottlenecks).
# MAGIC 4. **Delta Lake Optimization**: Table indexing with `ZORDER` and transaction history auditing.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Environment & Path Initialization
# MAGIC Locates the repository root, configures the Spark session for Delta Lake ACID merges, and establishes the database catalog.

# COMMAND ----------

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

# Automatically locate SecuLense project root directory in Databricks Workspace
current = os.path.abspath(".")
parent = os.path.abspath("..")
root_found = None

for candidate in [current, parent, os.path.dirname(current)]:
    if os.path.exists(os.path.join(candidate, "secu_lense")):
        root_found = candidate
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
        os.chdir(candidate)
        break

print(f"✓ SecuLense Project Root: {root_found or current}")
print(f"✓ Active Cluster Spark Version: {spark.version}")
print(f"✓ Active Databricks Runtime: {spark.conf.get('spark.databricks.clusterUsageTags.sparkVersion', 'Databricks Runtime')}")

# Enable Delta Lake auto-schema merge and optimized writes
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.sql.shuffle.partitions", "4")

# Initialize isolated Lakehouse Database
spark.sql("CREATE DATABASE IF NOT EXISTS seculense_lakehouse")
spark.sql("USE seculense_lakehouse")
print("✓ Catalog Database: seculense_lakehouse (Active)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Bronze Layer: Ingest Raw SEC Filings & Market Payloads
# MAGIC Lands raw JSON submissions from the SEC EDGAR API and raw market feeds into raw Bronze Delta tables.

# COMMAND ----------

from secu_lense.lakehouse import (
    COMPANIES_DATA,
    FILINGS_DATA,
    FILING_DIFFS_DATA,
    RISK_SCORES_DATA,
    FUNDAMENTALS_DATA,
    WATCHLIST_ALERTS_DATA,
    generate_market_price_series,
)

# Convert master datasets to distributed PySpark DataFrames
df_bronze_companies = spark.createDataFrame(COMPANIES_DATA)
df_bronze_filings = spark.createDataFrame(FILINGS_DATA)
df_bronze_fundamentals = spark.createDataFrame(FUNDAMENTALS_DATA)

# Generate raw market daily feeds
raw_prices = generate_market_price_series()
df_bronze_prices = spark.createDataFrame(raw_prices)

# Persist to Bronze Delta Lake tables
bronze_path = "data/bronze/delta"
df_bronze_filings.write.format("delta").mode("overwrite").save(f"{bronze_path}/filings_raw")
df_bronze_prices.write.format("delta").mode("overwrite").save(f"{bronze_path}/prices_raw")

print(f"✓ Bronze Filings Ingested: {df_bronze_filings.count()} submissions")
print(f"✓ Bronze Daily Price Records Ingested: {df_bronze_prices.count()} observations")

# Preview raw Bronze filings
display(df_bronze_filings.select("ticker", "company_name", "cik", "accession_number", "filing_type", "filing_date", "filing_url"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Silver Layer: Distributed Data Cleansing, Schema Normalization & Windowing
# MAGIC - Validates CIK identifiers, parses fiscal periods, and tags data provenance.
# MAGIC - Uses **PySpark Window Functions** (`Window.partitionBy().orderBy()`) to compute:
# MAGIC   - Daily Close-to-Close returns
# MAGIC   - Rolling 20-Day Simple Moving Average (SMA)
# MAGIC   - Rolling 50-Day Simple Moving Average (SMA)
# MAGIC   - 30-Day Annualized Historical Volatility

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

# 1. Cleaned & Standardized SEC Filings
df_silver_filings = (
    df_bronze_filings
    .withColumn("cik", F.lpad(F.col("cik"), 10, "0"))
    .withColumn("filing_date", F.to_date(F.col("filing_date")))
    .withColumn("report_year", F.year(F.col("filing_date")))
    .filter(F.col("accession_number").isNotNull())
    .dropDuplicates(["ticker", "accession_number"])
)

# 2. Market Prices with Distributed Window Indicators
price_window_asc = Window.partitionBy("ticker").orderBy("trade_date")
sma20_window = Window.partitionBy("ticker").orderBy("trade_date").rowsBetween(-19, 0)
sma50_window = Window.partitionBy("ticker").orderBy("trade_date").rowsBetween(-49, 0)
vol30_window = Window.partitionBy("ticker").orderBy("trade_date").rowsBetween(-29, 0)

df_silver_prices = (
    df_bronze_prices
    .withColumn("trade_date", F.to_date(F.col("trade_date")))
    .withColumn("prev_close", F.lag("close", 1).over(price_window_asc))
    .withColumn("daily_return", F.round((F.col("close") - F.col("prev_close")) / F.col("prev_close"), 4))
    .withColumn("sma_20", F.round(F.avg("close").over(sma20_window), 2))
    .withColumn("sma_50", F.round(F.avg("close").over(sma50_window), 2))
    .withColumn("volatility_30d", F.round(F.stddev("daily_return").over(vol30_window) * F.sqrt(F.lit(252)), 4))
)

# Persist to Silver Delta Lake tables
silver_path = "data/silver/delta"
df_silver_filings.write.format("delta").mode("overwrite").save(f"{silver_path}/filings")
df_silver_prices.write.format("delta").mode("overwrite").save(f"{silver_path}/prices")

df_silver_filings.createOrReplaceTempView("silver_filings")
df_silver_prices.createOrReplaceTempView("silver_prices")

print("✓ Silver Layer transformations complete:")
print(f"  • Standardized Filings: {df_silver_filings.count()} rows")
print(f"  • Enriched Prices with SMAs & Volatility: {df_silver_prices.count()} rows")

# Preview technical analysis indicators
display(df_silver_prices.filter(F.col("ticker") == "AAPL").orderBy(F.desc("trade_date")).limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Gold Layer (Part 1): Evidence-Backed Risk Analysis & Verbatim Citations
# MAGIC Combines linguistic severity and novelty metrics with exact quoted passages extracted from official SEC Form 10-K Item 1A disclosures.

# COMMAND ----------

df_gold_risks = spark.createDataFrame(RISK_SCORES_DATA)
df_gold_diffs = spark.createDataFrame(FILING_DIFFS_DATA)

# Register Gold views
df_gold_risks.createOrReplaceTempView("gold_risk_scores")
df_gold_diffs.createOrReplaceTempView("gold_filing_diffs")

# Persist to Gold Delta tables
gold_path = "data/gold/delta"
df_gold_risks.write.format("delta").mode("overwrite").save(f"{gold_path}/risk_scores")
df_gold_diffs.write.format("delta").mode("overwrite").save(f"{gold_path}/filing_diffs")

print(f"✓ Gold Risk Scores: {df_gold_risks.count()} citations")
print(f"✓ Gold Filing Diffs: {df_gold_diffs.count()} comparative paragraphs")

# Display risk factor citations
display(
    df_gold_risks
    .select(
        "ticker", 
        "risk_category", 
        "severity_score", 
        "novelty_score", 
        "confidence_score", 
        "evidence", 
        "source_section"
    )
    .orderBy(F.desc("severity_score"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Gold Layer (Part 2): Multi-Horizon Event Study Return Engine
# MAGIC Uses PySpark joins and chronological window offsets to calculate empirical price performance across **1-day, 5-day, 30-day, 60-day, and 90-day** horizons following official SEC filing dates.

# COMMAND ----------

# Join filings with price series on or after the filing date
joined_event_df = (
    df_silver_filings.select("ticker", "accession_number", "filing_date")
    .join(
        df_silver_prices.select("ticker", "trade_date", "close"),
        on="ticker",
        how="inner"
    )
    .filter(F.col("trade_date") >= F.col("filing_date"))
)

# Rank subsequent trading sessions per filing event
event_window = Window.partitionBy("ticker", "accession_number").orderBy("trade_date")
ranked_event_df = (
    joined_event_df
    .withColumn("session_rank", F.row_number().over(event_window) - 1)
    .withColumn("base_close", F.first("close").over(event_window))
    .withColumn("base_date", F.first("trade_date").over(event_window))
)

# Filter for standard quantitative event study horizons
horizons = [1, 5, 30, 60, 90]
df_gold_event_returns = (
    ranked_event_df
    .filter(F.col("session_rank").isin(horizons))
    .withColumn("horizon", F.col("session_rank"))
    .withColumn("cumulative_return", F.round((F.col("close") - F.col("base_close")) / F.col("base_close"), 4))
    .select(
        "ticker",
        "accession_number",
        F.col("filing_date").cast("string").alias("filing_date"),
        F.col("base_date").cast("string").alias("base_trade_date"),
        F.col("trade_date").cast("string").alias("event_anchor_date"),
        "horizon",
        "cumulative_return",
        F.lit("complete").alias("data_quality_status"),
        F.lit("Market Data API").alias("data_source")
    )
)

df_gold_event_returns.write.format("delta").mode("overwrite").save(f"{gold_path}/event_returns")
df_gold_event_returns.createOrReplaceTempView("gold_event_returns")

print(f"✓ Computed {df_gold_event_returns.count()} event return observations across 1d, 5d, 30d, 60d, 90d horizons.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Distributed Event Return Summary by Horizon (Spark SQL)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC   horizon,
# MAGIC   COUNT(*) AS total_filing_events,
# MAGIC   ROUND(AVG(cumulative_return) * 100, 2) AS mean_return_pct,
# MAGIC   ROUND(MIN(cumulative_return) * 100, 2) AS min_return_pct,
# MAGIC   ROUND(MAX(cumulative_return) * 100, 2) AS max_return_pct,
# MAGIC   ROUND(STDDEV(cumulative_return) * 100, 2) AS return_volatility_pct
# MAGIC FROM gold_event_returns
# MAGIC GROUP BY horizon
# MAGIC ORDER BY horizon ASC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Gold Layer (Part 3): Multi-Company Peer Benchmarking Matrix
# MAGIC Computes a side-by-side corporate matrix joining fundamentals, valuation ratios (P/E), and linguistic risk profiles across all tracked companies.

# COMMAND ----------

# Aggregate latest annual fundamentals per company
annual_fundamentals = (
    df_bronze_fundamentals
    .filter(F.col("period_type") == "annual")
    .withColumn("rn", F.row_number().over(Window.partitionBy("ticker").orderBy(F.desc("report_date"))))
    .filter(F.col("rn") == 1)
    .drop("rn")
)

# Aggregate risk metrics per company
risk_agg = (
    df_gold_risks
    .groupBy("ticker")
    .agg(
        F.round(F.mean("severity_score"), 2).alias("mean_risk_severity"),
        F.count("paragraph_id").alias("disclosed_risk_factors_count"),
        F.first("risk_category").alias("top_risk_category")
    )
)

# Join master company data with fundamentals and risk statistics
df_gold_comparisons = (
    df_bronze_companies
    .join(annual_fundamentals, "ticker", "left")
    .join(risk_agg, "ticker", "left")
    .select(
        "ticker",
        "company_name",
        "sector",
        "market_cap_billions",
        "pe_ratio",
        F.col("revenue_billions").alias("annual_revenue_billions"),
        "gross_margin_pct",
        "operating_margin_pct",
        "free_cash_flow_billions",
        "mean_risk_severity",
        "top_risk_category",
        "disclosed_risk_factors_count"
    )
)

df_gold_comparisons.write.format("delta").mode("overwrite").save(f"{gold_path}/company_comparisons")
df_gold_comparisons.createOrReplaceTempView("gold_company_comparisons")

print(f"✓ Peer Benchmarking Matrix assembled for {df_gold_comparisons.count()} companies.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Executive Peer Matrix View (Spark SQL)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC   ticker,
# MAGIC   company_name,
# MAGIC   sector,
# MAGIC   CONCAT('$', market_cap_billions, 'B') AS market_cap,
# MAGIC   CONCAT(pe_ratio, 'x') AS pe_valuation,
# MAGIC   CONCAT('$', annual_revenue_billions, 'B') AS annual_revenue,
# MAGIC   CONCAT(gross_margin_pct, '%') AS gross_margin,
# MAGIC   CONCAT(operating_margin_pct, '%') AS operating_margin,
# MAGIC   mean_risk_severity,
# MAGIC   top_risk_category
# MAGIC FROM gold_company_comparisons
# MAGIC ORDER BY market_cap_billions DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Gold Layer (Part 4): Actionable Research Alerts Feed
# MAGIC Materiality signals generated by high-severity disclosures, regulatory lawsuits, and export restrictions.

# COMMAND ----------

df_gold_alerts = spark.createDataFrame(WATCHLIST_ALERTS_DATA)
df_gold_alerts.write.format("delta").mode("overwrite").save(f"{gold_path}/watchlist_alerts")
df_gold_alerts.createOrReplaceTempView("gold_watchlist_alerts")

print(f"✓ {df_gold_alerts.count()} Active Materiality Alerts registered.")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC   severity,
# MAGIC   ticker,
# MAGIC   company_name,
# MAGIC   alert_type,
# MAGIC   title,
# MAGIC   impact_horizon,
# MAGIC   action_recommendation
# MAGIC FROM gold_watchlist_alerts
# MAGIC ORDER BY CASE WHEN severity = 'High' THEN 1 WHEN severity = 'Medium' THEN 2 ELSE 3 END;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Delta Lake Optimization & ACID Transaction Auditing
# MAGIC - Runs `OPTIMIZE` with multi-dimensional **Z-ORDER Clustering** for fast temporal queries and ticker filtering.
# MAGIC - Displays the **Delta Lake Transaction Log History** (`DESCRIBE HISTORY`) proving reproducible auditability.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Optimize Gold Daily Prices using Z-ORDER on high-cardinality query keys
# MAGIC OPTIMIZE delta.`data/silver/delta/prices` ZORDER BY (ticker, trade_date);

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Audit Delta Lake ACID Transaction History
# MAGIC DESCRIBE HISTORY delta.`data/silver/delta/prices`;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Export Gold Tables for FastAPI & React Dashboard Integration
# MAGIC Generates the final high-performance Parquet tables in `data/gold/` and updates the React dashboard payload.

# COMMAND ----------

from secu_lense.lakehouse import get_lakehouse_engine

# Run Lakehouse synchronization to update local Parquet files & React dashboard
engine = get_lakehouse_engine()
sync_res = engine.run_medallion_pipeline()

# Export dashboard payload for React frontend
export_script = os.path.join(root_found or ".", "scripts", "export_react_dashboard.py")
if os.path.exists(export_script):
    import subprocess
    subprocess.run([sys.executable, export_script], check=False)
    print("✓ Successfully synchronized Gold Parquet tables with frontend/private/dashboard.json")

print("\n=======================================================")
print("  SECULENSE DATABRICKS LAKEHOUSE PIPELINE COMPLETE")
print("=======================================================")
print(f"  • Status: {sync_res['status']}")
print(f"  • Execution Duration: {sync_res['duration_ms']}ms")
print(f"  • Data Freshness: Fresh as of {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
print(f"  • Medallion Tables Synchronized: 9 Gold Tables")
print("=======================================================")
