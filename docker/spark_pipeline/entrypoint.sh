#!/bin/bash
set -e
exec spark-submit \
  --master "${SPARK_MASTER:-local[*]}" \
  --packages "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3,org.postgresql:postgresql:42.7.3" \
  /app/streaming_job.py
