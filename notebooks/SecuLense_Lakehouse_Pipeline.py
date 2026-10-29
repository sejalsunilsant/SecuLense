# Databricks notebook source
# MAGIC %md
# MAGIC # SecuLense · Databricks Lakehouse Pipeline (Bronze → Silver → Gold)
# MAGIC 
# MAGIC This notebook runs the distributed **PySpark & Delta Lake** data pipeline for the SecuLense Financial Research Platform:
# MAGIC 1. **Bronze Layer**: Raw SEC EDGAR filing submissions and market data.
# MAGIC 2. **Silver Layer**: Cleaned, standardized, schema-validated corporate financials and price series.
# MAGIC 3. **Gold Layer**: Curated business analytics, paragraph-level filing diffs, evidence-backed risk analysis, peer comparisons, and actionable research alerts.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1. Setup & Dependencies

# COMMAND ----------

import os
import sys
from pathlib import Path

# Add project root to Python module path
root_dir = os.path.abspath("..")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

current_dir = os.path.abspath(".")
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

print(f"Working Directory: {os.getcwd()}")
print(f"Python Sys Path: {sys.path[:2]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2. Run the Medallion Lakehouse Pipeline
# MAGIC Ingests real SEC filings (AAPL, MSFT, NVDA, AMZN, GOOGL, TSLA), executes PySpark transformations, and writes Delta/Parquet tables to the Gold layer.

# COMMAND ----------

from secu_lense.lakehouse import get_lakehouse_engine

engine = get_lakehouse_engine()
result = engine.run_medallion_pipeline()

print(f"Status: {result.get('status')}")
print(f"Duration: {result.get('duration_ms')}ms")
print("\nGenerated Gold Tables:")
for table_name, count in result.get("freshness", {}).get("tables", {}).items():
    print(f"  • {table_name:25s}: {count:6d} records")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3. Register Delta Lake Tables in Spark Metastore / Unity Catalog
# MAGIC Registers the tables as Spark temporary SQL views so you can query them using Spark SQL or save them to Unity Catalog.

# COMMAND ----------

gold_dir = "data/gold"

tables = [
    "companies",
    "filings",
    "filing_diffs",
    "risk_scores",
    "daily_prices",
    "event_returns",
    "fundamentals",
    "company_comparisons",
    "watchlist_alerts",
]

for tbl in tables:
    path = f"{gold_dir}/{tbl}.parquet"
    if os.path.exists(path):
        df = spark.read.parquet(path)
        df.createOrReplaceTempView(f"seculense_{tbl}")
        print(f"Registered view: seculense_{tbl} ({df.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4. Multi-Company Peer Benchmarking Analysis (Spark SQL)
# MAGIC Compares market valuation, margins, revenue, and mean linguistic risk severity across market leaders.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC   ticker,
# MAGIC   company_name,
# MAGIC   sector,
# MAGIC   market_cap_billions,
# MAGIC   pe_ratio,
# MAGIC   annual_revenue_billions,
# MAGIC   gross_margin_pct,
# MAGIC   operating_margin_pct,
# MAGIC   mean_risk_severity,
# MAGIC   top_risk_category
# MAGIC FROM seculense_company_comparisons
# MAGIC ORDER BY market_cap_billions DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5. Evidence-Backed Risk Factors (Spark DataFrame)
# MAGIC Inspect verbatim quotations from Form 10-K Item 1A (Risk Factors) with severity and novelty scores.

# COMMAND ----------

df_risks = spark.table("seculense_risk_scores")
display(df_risks.select("ticker", "risk_category", "severity_score", "novelty_score", "evidence", "source_section"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6. Actionable Research Alerts
# MAGIC Material alerts triggered by high-severity regulatory investigations, supply constraints, and export controls.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 
# MAGIC   severity,
# MAGIC   ticker,
# MAGIC   alert_type,
# MAGIC   title,
# MAGIC   impact_horizon,
# MAGIC   trigger,
# MAGIC   action_recommendation
# MAGIC FROM seculense_watchlist_alerts
# MAGIC ORDER BY CASE WHEN severity = 'High' THEN 1 WHEN severity = 'Medium' THEN 2 ELSE 3 END;

# COMMAND ----------

# MAGIC %md
# MAGIC ### 7. Post-Filing Event Study Returns by Trading Horizon
# MAGIC Distributed aggregation measuring average return and volatility across 1-day, 5-day, 30-day, 60-day, and 90-day post-filing horizons.

# COMMAND ----------

from pyspark.sql import functions as F

df_events = spark.table("seculense_event_returns").filter(F.col("cumulative_return").isNotNull())

display(
    df_events.groupBy("horizon")
    .agg(
        F.count("*").alias("events_count"),
        F.round(F.avg("cumulative_return") * 100, 2).alias("avg_return_pct"),
        F.round(F.min("cumulative_return") * 100, 2).alias("min_return_pct"),
        F.round(F.max("cumulative_return") * 100, 2).alias("max_return_pct"),
        F.round(F.stddev("cumulative_return") * 100, 2).alias("volatility_pct")
    )
    .orderBy("horizon")
)

