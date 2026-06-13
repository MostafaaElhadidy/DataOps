# Runbook: Kafka Consumer Lag High

## Symptoms
- Prometheus alert `KafkaConsumerLagHigh` is firing (lag > 1000)
- Dashboard shows growing lag on topic `pipeline-events`
- PostgreSQL `events` table row rate slowing down or stopped
- Spark streaming job showing long batch processing times

## Root Cause Categories
- Spark worker down (consumer stopped)
- Consumer processing is too slow (CPU/memory bottleneck)
- Spike in producer throughput beyond consumer capacity
- Kafka partition imbalance (all load on one partition)
- Deserialization errors causing consumer to skip/retry

## Diagnosis Steps
1. Check consumer group status: `kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group spark-streaming`
2. Check Spark worker health: `curl -sf http://localhost:8090/`
3. Check batch processing time in Spark UI
4. Look at consumer logs: `docker logs aiops-spark-pipeline --tail 100`
5. Measure partition distribution: `kafka-topics.sh --describe --topic pipeline-events --bootstrap-server localhost:9092`

## Remediation

### If Spark worker is down
Restart it (see spark_worker_down.md), lag will drain automatically.

### If consumer is slow (high batch time)
Increase Spark worker resources in docker-compose.yml:
```yaml
SPARK_WORKER_MEMORY: 4G
SPARK_WORKER_CORES: 4
```

### If partitions are imbalanced
Increase partitions (non-destructive for new messages):
```bash
kafka-topics.sh --alter --topic pipeline-events --partitions 6 --bootstrap-server localhost:9092
```

### Temporary: pause the producer to let consumer catch up
```bash
docker stop aiops-data-generator
# wait for lag to drain
docker start aiops-data-generator
```

## Validation
- `kafka_consumer_group_lag{topic="pipeline-events"}` drops below 100
- New rows continue appearing in PostgreSQL
- Alert clears automatically when lag < threshold

## MTTR Target
< 10 minutes if root cause is a stopped consumer
