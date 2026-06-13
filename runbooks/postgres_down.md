# Runbook: PostgreSQL Down

## Symptoms
- Prometheus alert `PostgresDown` is firing
- `pg_isready` returns "no response"
- Spark pipeline logs show JDBC connection errors
- Airflow DAG `check_data_freshness` failing with connection refused

## Root Cause Categories
- Container crashed (OOM, disk full, or misconfiguration)
- Data directory corruption
- Max connections exceeded and PostgreSQL rejected new connections
- PostgreSQL process killed externally

## Diagnosis Steps
1. Check container status: `docker inspect aiops-postgres | jq '.[0].State'`
2. Check PostgreSQL logs: `docker logs aiops-postgres --tail 100`
3. Check disk space: `docker exec aiops-postgres df -h /var/lib/postgresql/data`
4. Check active connections before failure: review Prometheus `pg_stat_activity_count`
5. Check exit code for OOM: `docker inspect aiops-postgres | jq '.[0].State.OOMKilled'`

## Remediation

### Primary Action (container restart)
```bash
docker restart aiops-postgres
```

### If disk full
```bash
# Check disk usage inside container
docker exec aiops-postgres du -sh /var/lib/postgresql/data
# On host: free space, then restart
docker system prune -f --volumes  # WARNING: removes unused volumes
docker restart aiops-postgres
```

### If max_connections exceeded (too many idle connections)
After restart, terminate idle connections:
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < NOW() - INTERVAL '5 minutes';
```

### If data corruption suspected
Do NOT restart. Take a snapshot of the data volume first:
```bash
docker stop aiops-postgres
# Backup volume before any repair
docker run --rm -v aiops_postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/pg_backup.tar.gz /data
```

## Validation
- `pg_isready -U pipeline -d pipeline` returns "accepting connections"
- `up{job="postgres"}` returns 1 in Prometheus
- Spark pipeline resumes writing (new rows in `events` table)
- Airflow DAG completes successfully

## MTTR Target
< 3 minutes for a simple restart
