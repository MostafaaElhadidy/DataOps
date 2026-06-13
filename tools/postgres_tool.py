"""PostgreSQL tool — query execution and connectivity health check."""

from typing import Any

import psycopg
import psycopg.rows

from core.config import settings
from core.observability import get_logger

logger = get_logger("postgres_tool")


def _dsn() -> str:
    s = settings
    return (
        f"host={s.postgres_host} port={s.postgres_port} "
        f"dbname={s.postgres_db} user={s.postgres_user} "
        f"password={s.postgres_password}"
    )


async def execute_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    async with await psycopg.AsyncConnection.connect(_dsn()) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql, params)
            if cur.description:
                return await cur.fetchall()
    return []


async def health_check() -> dict[str, Any]:
    try:
        rows = await execute_query("SELECT 1 AS alive")
        return {"healthy": bool(rows), "message": "connected"}
    except Exception as exc:
        logger.error("postgres_health_failed", error=str(exc))
        return {"healthy": False, "message": str(exc)}


async def get_connection_count() -> int:
    rows = await execute_query(
        "SELECT count(*) AS cnt FROM pg_stat_activity WHERE datname = %s",
        (settings.postgres_db,),
    )
    return rows[0]["cnt"] if rows else 0


async def get_recent_events(limit: int = 10) -> list[dict]:
    return await execute_query(
        "SELECT * FROM events ORDER BY event_time DESC LIMIT %s", (limit,)
    )
