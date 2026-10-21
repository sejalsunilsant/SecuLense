"""Optional PySpark transformation entry point."""
def process_filings(input_path:str,output_path:str,master="local[*]"):
    try: from pyspark.sql import SparkSession, functions as F
    except ImportError as exc: raise RuntimeError("Install SecuLense with [spark] to run distributed jobs") from exc
    spark=SparkSession.builder.master(master).appName("SecuLense").getOrCreate()
    try:
        df=spark.read.parquet(input_path).withColumn("ticker",F.upper(F.col("ticker")))
        df.dropDuplicates(["ticker","accession_number","section_name","paragraph_id"]).write.mode("overwrite").partitionBy("ticker").parquet(output_path)
    finally: spark.stop()
