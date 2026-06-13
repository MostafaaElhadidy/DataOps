"""Docker tool — container lifecycle management with allowlist enforcement."""

import docker

from core.observability import get_logger

logger = get_logger("docker_tool")

ALLOWED_ACTIONS = {"restart", "start", "stop"}
BLOCKED_KEYWORDS = {"delete", "rm", "remove", "drop", "truncate", "format", "kill"}


def _client() -> docker.DockerClient:
    return docker.from_env()


def _validate_action(action: str) -> None:
    if action.lower() not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Action '{action}' is not allowed. Permitted: {ALLOWED_ACTIONS}"
        )


def _validate_command(command: str) -> None:
    lowered = command.lower()
    for kw in BLOCKED_KEYWORDS:
        if kw in lowered:
            raise ValueError(f"Blocked keyword '{kw}' found in command: {command!r}")


def container_status(name: str) -> dict:
    try:
        c = _client().containers.get(name)
        return {"name": c.name, "status": c.status, "id": c.short_id}
    except docker.errors.NotFound:
        return {"name": name, "status": "not_found", "id": None}


def restart_container(name: str, dry_run: bool = False) -> dict:
    _validate_action("restart")
    if dry_run:
        logger.info("dry_run", action="restart", container=name)
        return {"action": "restart", "container": name, "dry_run": True, "status": "skipped"}
    try:
        _client().containers.get(name).restart()
        logger.info("container_restarted", container=name)
        return {"action": "restart", "container": name, "status": "success"}
    except Exception as exc:
        logger.error("restart_failed", container=name, error=str(exc))
        return {"action": "restart", "container": name, "status": "failed", "error": str(exc)}


def start_container(name: str, dry_run: bool = False) -> dict:
    _validate_action("start")
    if dry_run:
        return {"action": "start", "container": name, "dry_run": True, "status": "skipped"}
    try:
        _client().containers.get(name).start()
        return {"action": "start", "container": name, "status": "success"}
    except Exception as exc:
        return {"action": "start", "container": name, "status": "failed", "error": str(exc)}


def stop_container(name: str, dry_run: bool = False) -> dict:
    _validate_action("stop")
    if dry_run:
        return {"action": "stop", "container": name, "dry_run": True, "status": "skipped"}
    try:
        _client().containers.get(name).stop()
        return {"action": "stop", "container": name, "status": "success"}
    except Exception as exc:
        return {"action": "stop", "container": name, "status": "failed", "error": str(exc)}


def execute_command(name: str, command: str, dry_run: bool = False) -> dict:
    """Run a validated shell command inside a container."""
    _validate_command(command)
    if dry_run:
        return {"command": command, "container": name, "dry_run": True, "status": "skipped"}
    try:
        result = _client().containers.get(name).exec_run(command)
        return {
            "command": command,
            "container": name,
            "exit_code": result.exit_code,
            "output": result.output.decode("utf-8", errors="replace"),
            "status": "success" if result.exit_code == 0 else "failed",
        }
    except Exception as exc:
        return {"command": command, "container": name, "status": "failed", "error": str(exc)}
