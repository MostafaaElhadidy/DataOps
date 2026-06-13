"""Synthetic data generator — pushes IoT-style events to Kafka."""

import json
import os
import random
import time
from datetime import UTC, datetime

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "pipeline-events")
RATE_HZ = float(os.getenv("EVENT_RATE_HZ", "2"))  # events per second

SENSORS = [f"sensor_{i:02d}" for i in range(1, 21)]


def make_event() -> dict:
    return {
        "event_id": f"E{random.randint(10_000, 99_999)}",
        "timestamp": datetime.now(UTC).isoformat(),
        "sensor_id": random.choice(SENSORS),
        "temperature": round(random.gauss(55.0, 15.0), 2),
        "pressure": round(random.uniform(1.0, 10.0), 2),
        "status": random.choices(["ok", "warning", "error"], weights=[85, 10, 5])[0],
        "value": round(random.uniform(0, 1000), 2),
    }


def connect(retries: int = 10, delay: float = 5.0) -> KafkaProducer:
    for attempt in range(retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            print(f"Connected to Kafka at {BOOTSTRAP}")
            return producer
        except NoBrokersAvailable:
            print(f"Kafka not ready, retry {attempt + 1}/{retries} in {delay}s …")
            time.sleep(delay)
    raise RuntimeError("Could not connect to Kafka after retries.")


def main():
    producer = connect()
    interval = 1.0 / RATE_HZ
    print(f"Generating events → {TOPIC} at {RATE_HZ} Hz")
    while True:
        event = make_event()
        producer.send(TOPIC, value=event)
        time.sleep(interval)


if __name__ == "__main__":
    main()
