"""Log retrieval tool — reads container logs via the Docker SDK."""

import docker

from core.observability import get_logger

logger = get_logger("logs_tool")

CONTAINER_MAP = {
    "spark": "aiops-spark-worker",
    "spark-master": "aiops-spark-master",
    "kafka": "aiops-kafka",
    "postgres": "aiops-postgres",
    "airflow": "aiops-airflow-scheduler",
    "airflow-webserver": "aiops-airflow-webserver",
}


def _client() -> docker.DockerClient:
    return docker.from_env()


def get_logs(service: str, tail: int = 200) -> str:
    """Fetch the last `tail` lines of logs for a service container."""
    name = CONTAINER_MAP.get(service, service)
    try:
        c = _client().containers.get(name)
        return c.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
    except docker.errors.NotFound:
        return f"[logs_tool] Container '{name}' not found."
    except Exception as exc:
        logger.error("log_fetch_failed", service=service, error=str(exc))
        return f"[logs_tool] Error: {exc}"


def get_spark_logs(tail: int = 200) -> str:
    return get_logs("spark", tail)


def get_kafka_logs(tail: int = 200) -> str:
    return get_logs("kafka", tail)


def get_postgres_logs(tail: int = 200) -> str:
    return get_logs("postgres", tail)


def get_airflow_logs(tail: int = 200) -> str:
    return get_logs("airflow", tail)
