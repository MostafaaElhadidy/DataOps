"""Airflow DAG: monitors data freshness and runs hourly aggregations."""

from __future__ import annotations

from datetime import datetime, timedelta

import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator

PG_CONN = {
    "host": "postgres",
    "port": 5432,
    "dbname": "pipeline",
    "user": "pipeline",
    "password": "pipeline_secret",
}

default_args = {
    "owner": "aiops",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


def check_data_freshness(**ctx):
    conn = psycopg2.connect(**PG_CONN)
    cur = conn.cursor()
    cur.execute(
        "SELECT MAX(event_time) FROM events WHERE event_time > NOW() - INTERVAL '5 minutes'"
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row[0] is None:
        raise ValueError("No events in the last 5 minutes — pipeline may be stalled!")
    print(f"Latest event at: {row[0]}")


def compute_hourly_stats(**ctx):
    conn = psycopg2.connect(**PG_CONN)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO hourly_stats (hour_bucket, sensor_id, avg_temp, avg_pressure, event_count)
        SELECT
            DATE_TRUNC('hour', event_time) AS hour_bucket,
            sensor_id,
            AVG(temperature),
            AVG(pressure),
            COUNT(*)
        FROM events
        WHERE event_time >= DATE_TRUNC('hour', NOW()) - INTERVAL '1 hour'
          AND event_time <  DATE_TRUNC('hour', NOW())
        GROUP BY 1, 2
        ON CONFLICT DO NOTHING
        """
    )
    conn.commit()
    cur.close()
    conn.close()
    print("Hourly stats computed.")


def check_schema(**ctx):
    conn = psycopg2.connect(**PG_CONN)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'events' ORDER BY ordinal_position
        """
    )
    columns = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    expected = {"id", "event_id", "event_time", "sensor_id", "temperature",
                "pressure", "status", "value", "created_at"}
    missing = expected - set(columns)
    if missing:
        raise ValueError(f"Schema drift detected! Missing columns: {missing}")
    print(f"Schema OK: {columns}")


with DAG(
    dag_id="pipeline_health",
    default_args=default_args,
    description="Pipeline freshness, aggregation, and schema checks",
    schedule="*/5 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["aiops", "pipeline"],
) as dag:

    t_freshness = PythonOperator(
        task_id="check_data_freshness",
        python_callable=check_data_freshness,
    )

    t_schema = PythonOperator(
        task_id="check_schema",
        python_callable=check_schema,
    )

    t_stats = PythonOperator(
        task_id="compute_hourly_stats",
        python_callable=compute_hourly_stats,
    )

    t_freshness >> t_schema >> t_stats
