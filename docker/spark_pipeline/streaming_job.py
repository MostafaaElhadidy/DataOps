"""PySpark Structured Streaming job: Kafka → PostgreSQL."""

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp
from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
)

SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "pipeline-events")
PG_URL = os.getenv("POSTGRES_URL", "jdbc:postgresql://localhost:5432/pipeline")
PG_USER = os.getenv("POSTGRES_USER", "pipeline")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "pipeline_secret")

EVENT_SCHEMA = StructType(
    [
        StructField("event_id", StringType()),
        StructField("timestamp", StringType()),
        StructField("sensor_id", StringType()),
        StructField("temperature", DoubleType()),
        StructField("pressure", DoubleType()),
        StructField("status", StringType()),
        StructField("value", DoubleType()),
    ]
)


def write_batch(df, epoch_id: int) -> None:
    (
        df.write.format("jdbc")
        .option("url", PG_URL)
        .option("dbtable", "events")
        .option("user", PG_USER)
        .option("password", PG_PASSWORD)
        .option("driver", "org.postgresql.Driver")
        .mode("append")
        .save()
    )


def main():
    spark = (
        SparkSession.builder.appName("AIOps-Pipeline")
        .master(SPARK_MASTER)
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3,"
            "org.postgresql:postgresql:42.7.3",
        )
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    parsed = raw.select(
        from_json(col("value").cast("string"), EVENT_SCHEMA).alias("d")
    ).select("d.*").withColumn("event_time", to_timestamp("timestamp"))

    query = (
        parsed.writeStream.foreachBatch(write_batch)
        .option("checkpointLocation", "/tmp/spark-checkpoint")
        .trigger(processingTime="10 seconds")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
