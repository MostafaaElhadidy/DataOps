"""Kafka tool — topic inspection and consumer lag measurement."""

from kafka import KafkaAdminClient, KafkaConsumer
from kafka.structs import TopicPartition

from core.config import settings
from core.observability import get_logger

logger = get_logger("kafka_tool")


def _admin() -> KafkaAdminClient:
    return KafkaAdminClient(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        request_timeout_ms=5000,
    )


def list_topics() -> list[str]:
    admin = _admin()
    topics = admin.list_topics()
    admin.close()
    return sorted(t for t in topics if not t.startswith("__"))


def consumer_lag(group_id: str = "spark-streaming") -> dict:
    """Return per-partition lag for a consumer group."""
    admin = _admin()
    try:
        offsets = admin.list_consumer_group_offsets(group_id)
    except Exception as exc:
        admin.close()
        logger.warning("consumer_lag_failed", group=group_id, error=str(exc))
        return {"group": group_id, "error": str(exc), "total_lag": -1}
    admin.close()

    consumer = KafkaConsumer(bootstrap_servers=settings.kafka_bootstrap_servers)
    partitions = list(offsets.keys())
    end_offsets = consumer.end_offsets(partitions)
    consumer.close()

    lag_info, total = [], 0
    for tp, meta in offsets.items():
        lag = end_offsets.get(tp, 0) - meta.offset
        lag_info.append({"topic": tp.topic, "partition": tp.partition, "lag": lag})
        total += lag

    return {"group": group_id, "partitions": lag_info, "total_lag": total}


def health_check() -> dict:
    try:
        topics = list_topics()
        return {"healthy": True, "topics": topics}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}
