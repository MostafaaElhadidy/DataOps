# Runbook: Schema Drift Detected

## Symptoms
- Airflow DAG `check_schema` task fails with "Schema drift detected"
- Spark pipeline throwing `AnalysisException` or field-not-found errors
- New events not being written to PostgreSQL (silently dropped)
- Data in `events` table shows NULL values in unexpected columns

## Root Cause Categories
- Producer-side change: new field added or field renamed in the event schema
- PostgreSQL DDL change: column dropped, renamed, or type changed
- Spark schema mismatch: schema defined in `streaming_job.py` differs from actual Kafka payload

## Diagnosis Steps
1. Compare current table schema with expected:
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'events'
ORDER BY ordinal_position;
```
2. Inspect a recent raw Kafka message:
```bash
kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic pipeline-events --max-messages 1 --from-beginning
```
3. Compare against the schema in `docker/spark_pipeline/streaming_job.py`

## Remediation

### If new column was added to the producer
Add the column to PostgreSQL:
```sql
ALTER TABLE events ADD COLUMN new_field_name VARCHAR(100);
```
Then update `EVENT_SCHEMA` in `streaming_job.py` and restart the pipeline:
```bash
docker restart aiops-spark-pipeline
```

### If a column was renamed
```sql
ALTER TABLE events RENAME COLUMN old_name TO new_name;
```
Update `streaming_job.py` accordingly and restart.

### If a column was dropped unintentionally
Restore from backup or re-create with NULL default:
```sql
ALTER TABLE events ADD COLUMN restored_column VARCHAR(100) DEFAULT NULL;
```

### Reset the Spark checkpoint (if schema change is backward-incompatible)
```bash
docker exec aiops-spark-pipeline rm -rf /tmp/spark-checkpoint
docker restart aiops-spark-pipeline
```

## Validation
- Airflow `check_schema` task passes
- Spark pipeline resumes writing without errors
- New events contain all expected fields (no unexpected NULLs)
- No `AnalysisException` in Spark logs

## Prevention
- Version the producer schema (use Confluent Schema Registry or Avro)
- Add a schema validation step to the CI pipeline for the producer
- Run `check_schema` DAG task every 5 minutes (already scheduled)
