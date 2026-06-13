# Runbook: Airflow DAG Failure

## Symptoms
- Airflow UI shows DAG `pipeline_health` in "failed" state
- Alert `AirflowDown` firing or Airflow webserver unreachable
- Pipeline health checks not running; freshness gaps undetected
- Email/Slack notifications from Airflow (if configured)

## Root Cause Categories
- Airflow scheduler not running (container down)
- Python dependency missing in the Airflow worker environment
- DAG task error: database connection failure, SQL error, or logic bug
- Airflow metadata database (postgres-airflow) unreachable
- Resource exhaustion (disk full, OOM)

## Diagnosis Steps
1. Check scheduler container: `docker logs aiops-airflow-scheduler --tail 100`
2. Check webserver: `curl http://localhost:8080/health`
3. Check task logs in Airflow UI: DAGs → pipeline_health → task log
4. Verify metadata DB: `docker exec aiops-postgres-airflow pg_isready -U airflow`
5. Check for import errors: `docker exec aiops-airflow-scheduler airflow dags list-import-errors`

## Remediation

### If scheduler is down
```bash
docker restart aiops-airflow-scheduler
```

### If webserver is down
```bash
docker restart aiops-airflow-webserver
```

### If DAG has a Python import error
Fix the DAG file in `docker/airflow/dags/`, then:
```bash
docker exec aiops-airflow-scheduler airflow dags reserialize
```

### If metadata DB connection failed
```bash
docker restart aiops-postgres-airflow
# Wait for it to be healthy, then:
docker restart aiops-airflow-scheduler aiops-airflow-webserver
```

### Manually re-trigger the failed DAG run
Via API:
```bash
curl -X POST http://localhost:8080/api/v1/dags/pipeline_health/dagRuns \
  -H "Content-Type: application/json" \
  -u airflow:airflow \
  -d '{"conf": {}}'
```

## Validation
- `curl http://localhost:8080/health` returns `{"status":"healthy"}`
- DAG `pipeline_health` shows a successful run in the last 10 minutes
- All three tasks (check_data_freshness, check_schema, compute_hourly_stats) are green

## MTTR Target
< 5 minutes for scheduler restart
