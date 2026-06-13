from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # LLM
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "not-needed"
    llm_model_heavy: str = "qwen2.5:32b"
    llm_model_standard: str = "qwen2.5:14b"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "pipeline-events"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "pipeline"
    postgres_user: str = "pipeline"
    postgres_password: str = "pipeline_secret"

    # Prometheus
    prometheus_url: str = "http://localhost:9090"

    # Airflow
    airflow_base_url: str = "http://localhost:8080"
    airflow_user: str = "airflow"
    airflow_password: str = "airflow"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "runbooks"

    # Web search
    tavily_api_key: str = ""

    # Observability
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "aiops-platform"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8001

    # Safety
    max_retries: int = 3
    dry_run: bool = False
    hitl_enabled: bool = True

    # Paths
    reports_dir: str = "reports"
    incidents_dir: str = "incidents"


settings = Settings()
