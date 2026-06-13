import logging
import os
import sys
from datetime import UTC, datetime

import structlog

from core.config import settings


def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project


def get_logger(name: str, incident_id: str = ""):
    log = structlog.get_logger(name)
    if incident_id:
        log = log.bind(incident_id=incident_id)
    return log


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def make_timeline_event(agent: str, action: str, details: str) -> dict:
    return {
        "timestamp": now_iso(),
        "agent": agent,
        "action": action,
        "details": details,
    }


setup_logging()
