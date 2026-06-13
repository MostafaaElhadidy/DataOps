# Runbook: Spark Worker Down

## Symptoms
- Prometheus alert `SparkWorkerDown` or `SparkNoWorkers` is firing
- Spark UI shows 0 active workers
- Streaming job is stalled; no new rows appearing in PostgreSQL
- Kafka consumer lag is growing rapidly

## Root Cause Categories
- Container OOM-killed (heap too large, no memory limit)
- Container exited due to application error or unhandled exception
- Network partition between Spark master and worker
- Disk full on the worker node

## Diagnosis Steps
1. Check container status: `docker inspect aiops-spark-worker | jq '.[0].State'`
2. Check exit code: `docker inspect aiops-spark-worker | jq '.[0].State.ExitCode'`
3. Tail logs for OOM or exception: `docker logs aiops-spark-worker --tail 100`
4. Verify master still healthy: `curl -sf http://localhost:8090/` 
5. Check disk space: `df -h` on the host

## Remediation

### Primary Action (container restart)
```bash
docker restart aiops-spark-worker
```

### If OOM (ExitCode 137)
Increase memory allocation in docker-compose.yml:
```yaml
environment:
  SPARK_WORKER_MEMORY: 4G
```
Then restart.

### If disk full
Free space on the host, then restart:
```bash
docker system prune -f
docker restart aiops-spark-worker
```

## Validation
- Spark UI (http://localhost:8090) shows 1+ active workers
- `up{job="spark"}` returns 1 in Prometheus
- New rows appear in PostgreSQL `events` table within 30 seconds
- Kafka consumer lag starts decreasing

## MTTR Target
< 5 minutes for a simple container restart

## Prevention
- Set resource limits in docker-compose: `mem_limit: 3g`
- Add container restart policy: `restart: unless-stopped`
- Alert on lag > 500 before it reaches 1000
