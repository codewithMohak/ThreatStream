
from pathlib import Path
import pandas as pd

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, sum as spark_sum,
    to_timestamp, window, when
)

# Project folders
ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "access_logs.csv"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Log file not found: {INPUT_FILE}\n"
        "Run the Go log generator first."
    )

# Start Spark locally
spark = (
    SparkSession.builder
    .appName("ThreatStream")
    .master("local[2]")
    .config("spark.ui.enabled", "false")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

try:
    # Read and prepare web logs
    logs = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(str(INPUT_FILE))
        .withColumn("timestamp", to_timestamp("timestamp"))
        .withColumn("status", col("status").cast("integer"))
        .withColumn(
            "response_bytes",
            col("response_bytes").cast("integer")
        )
        .na.drop(
            subset=[
                "timestamp", "ip", "method",
                "endpoint", "status"
            ]
        )
        .cache()
    )

    total = logs.count()

    if total == 0:
        raise ValueError("The log file contains no valid records.")

    # 1. Overall summary
    summary = logs.agg(
        count("*").alias("total_requests"),
        # approx-free exact distinct IP count
        # Use countDistinct through a separate aggregation below.
        spark_sum(
            when(col("status") >= 400, 1).otherwise(0)
        ).alias("error_requests"),
        spark_sum(
            when(col("status") >= 500, 1).otherwise(0)
        ).alias("server_errors"),
        spark_sum(
            when(col("status") == 401, 1).otherwise(0)
        ).alias("unauthorized_requests"),
        spark_sum(
            when(col("status") == 403, 1).otherwise(0)
        ).alias("forbidden_requests"),
    ).toPandas()

    from pyspark.sql.functions import countDistinct

    unique_ips = logs.agg(
        countDistinct("ip").alias("unique_ips")
    ).first()["unique_ips"]

    summary["unique_ips"] = unique_ips
    summary.to_csv(OUTPUT_DIR / "summary.csv", index=False)

    # 2. Requests by IP
    ip_summary = (
        logs.groupBy("ip")
        .agg(
            count("*").alias("requests"),
            spark_sum(
                when(col("status") == 401, 1).otherwise(0)
            ).alias("failed_logins"),
            spark_sum(
                when(col("status") == 403, 1).otherwise(0)
            ).alias("forbidden_requests"),
            spark_sum(
                when(col("status") == 404, 1).otherwise(0)
            ).alias("not_found_requests"),
        )
        .orderBy(col("requests").desc())
    )

    # 3. Requests by endpoint
    endpoint_summary = (
        logs.groupBy("endpoint")
        .agg(count("*").alias("requests"))
        .orderBy(col("requests").desc())
    )

    # 4. HTTP status distribution
    status_summary = (
        logs.groupBy("status")
        .agg(count("*").alias("requests"))
        .orderBy("status")
    )

    # 5. Suspicious IP detection rules
    suspicious_endpoints = [
        "/admin", "/.env", "/wp-login.php",
        "/config", "/backup"
    ]

    alerts = (
        logs.groupBy("ip")
        .agg(
            count("*").alias("requests"),
            spark_sum(
                when(col("status") == 401, 1).otherwise(0)
            ).alias("failed_logins"),
            spark_sum(
                when(col("status") == 403, 1).otherwise(0)
            ).alias("forbidden_requests"),
            spark_sum(
                when(
                    col("endpoint").isin(suspicious_endpoints),
                    1
                ).otherwise(0)
            ).alias("suspicious_paths"),
        )
        .withColumn(
            "reason",
            when(
                col("failed_logins") >= 5,
                "Repeated failed logins"
            ).when(
                col("suspicious_paths") >= 3,
                "Repeated suspicious endpoint access"
            ).when(
                col("forbidden_requests") >= 5,
                "Repeated forbidden access"
            ).when(
                col("requests") >= 100,
                "High request volume"
            ).otherwise(None)
        )
        .filter(col("reason").isNotNull())
        .orderBy(col("requests").desc())
    )

    # 6. Requests over time, grouped into 5-minute windows
    timeline = (
        logs.groupBy(
            window(col("timestamp"), "5 minutes")
        )
        .agg(count("*").alias("requests"))
        .select(
            col("window.start").alias("time"),
            "requests"
        )
        .orderBy("time")
    )

    # Save small aggregated results as dashboard-friendly CSVs
    ip_summary.toPandas().to_csv(
        OUTPUT_DIR / "ip_summary.csv", index=False
    )
    endpoint_summary.toPandas().to_csv(
        OUTPUT_DIR / "endpoint_summary.csv", index=False
    )
    status_summary.toPandas().to_csv(
        OUTPUT_DIR / "status_summary.csv", index=False
    )
    alerts.toPandas().to_csv(
        OUTPUT_DIR / "alerts.csv", index=False
    )
    timeline.toPandas().to_csv(
        OUTPUT_DIR / "timeline_summary.csv", index=False
    )

    print("\n===== THREATSTREAM ANALYTICS =====")
    print(f"Records processed: {total}")
    print(f"Unique IP addresses: {unique_ips}")
    print(f"Suspicious IPs flagged: {alerts.count()}")
    print(f"Results saved to: {OUTPUT_DIR}")

finally:
    spark.stop()
