"""Structured, per-agent timing and audit callbacks for Google ADK."""

import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from .privacy import mask_pii

logger = logging.getLogger(__name__)
_lock = threading.RLock()
_agent_started: dict[tuple[str, str], float] = {}
_agent_usage: dict[tuple[str, str], dict[str, int]] = {}
_APPLICATION_ID = re.compile(
    r"(LA-\d{8}-[A-F0-9]{6}|PA-SYN-[A-Z0-9-]+?)(?=-attempt-\d|$)"
)


def before_agent(context: Any) -> None:
    """Capture a start time keyed by ADK invocation and agent name."""
    with _lock:
        _agent_started[_agent_key(context)] = time.perf_counter()


def after_model(context: Any, response: Any) -> None:
    """Accumulate provider token usage when the response exposes it."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return
    key = _agent_key(context)
    with _lock:
        counts = _agent_usage.setdefault(key, {})
        counts["input_tokens"] = counts.get("input_tokens", 0) + int(
            getattr(usage, "prompt_token_count", 0) or 0
        )
        counts["output_tokens"] = counts.get("output_tokens", 0) + int(
            getattr(usage, "candidates_token_count", 0) or 0
        )


def after_agent(context: Any) -> None:
    """Log and audit the agent's output, elapsed time, and any model error."""
    key = _agent_key(context)
    with _lock:
        started = _agent_started.pop(key, None)
        token_usage = _agent_usage.pop(key, {})
    event = _event_base(context)
    event.update(
        {
            "latency_ms": round(
                max(0.0, time.perf_counter() - started) * 1000, 3
            )
            if started is not None
            else None,
            "token_usage": token_usage,
            "output": mask_pii(_output_text(getattr(context, "output", None)) or ""),
            "errors": (
                [mask_pii(str(context.error))]
                if getattr(context, "error", None)
                else []
            ),
        }
    )
    _record(event)


def on_model_error(context: Any, request: Any, error: Exception) -> None:
    """Record a model-call error without suppressing it."""
    event = _event_base(context)
    event.update(
        {
            "latency_ms": None,
            "token_usage": {},
            "output": None,
            "errors": [mask_pii(f"{type(error).__name__}: {error}")],
        }
    )
    _record(event)


def _agent_key(context: Any) -> tuple[str, str]:
    return (
        str(getattr(context, "invocation_id", "")),
        str(getattr(context, "agent_name", "unknown")),
    )


def _event_base(context: Any) -> dict[str, Any]:
    user_content = mask_pii(_output_text(getattr(context, "user_content", None)) or "")
    session = getattr(context, "session", None)
    session_id = str(getattr(session, "id", ""))
    match = _APPLICATION_ID.search(session_id)
    if match is None:
        state = getattr(context, "state", {})
        application_id = str(state.get("application_id", "unknown"))
    else:
        application_id = match.group(0)
    return {
        "application_id": application_id,
        "agent_name": str(getattr(context, "agent_name", "unknown")),
        "input_hash": hashlib.sha256(user_content.encode("utf-8")).hexdigest(),
    }


def _output_text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), sort_keys=True)
    parts = getattr(value, "parts", None)
    if parts is not None:
        return "".join(
            str(part.text)
            for part in parts
            if getattr(part, "text", None) is not None
        )
    return str(value)


def _record(event: dict[str, Any]) -> None:
    record = {**event, "timestamp": time.time()}
    logger.info("%s", json.dumps(record, sort_keys=True, default=str))
    application_id = str(record["application_id"])
    if application_id == "unknown":
        return
    _append_audit_event(application_id, record)


def _append_audit_event(application_id: str, event: dict[str, Any]) -> None:
    audit_dir = Path(os.getenv("AUDIT_DIR", "audit"))
    audit_dir.mkdir(parents=True, exist_ok=True)
    destination = audit_dir / f"{application_id}.json"
    temporary = destination.with_suffix(".json.tmp")
    with _lock:
        if destination.exists():
            payload = json.loads(destination.read_text(encoding="utf-8"))
        else:
            payload = {
                "application_id": application_id,
                "created_at": time.time(),
                "events": [],
            }
        payload["events"].append(event)
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(destination)
