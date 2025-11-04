from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from dt.alerts.config.alert_rule import SeverityLevel
from dt.communication.dataclasses.serializable import JsonSerializable


@dataclass
class CandidateAlert(JsonSerializable):
    """Represents a potential alert produced by rule evaluation or submissions."""

    alert_id: str
    rule_id: str | None
    source: str
    severity: SeverityLevel
    message: str
    correlation_id: str
    payload: dict[str, Any]
    persistence_count: int
    cooldown_seconds: int

    @classmethod
    def from_submission_dict(cls, data: dict[str, Any]) -> "CandidateAlert":
        """Create a candidate alert from an external submission payload."""

        required = {"alert_id", "source", "severity", "message", "correlation_id"}
        missing = required - data.keys()
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"Missing required fields: {missing_list}")

        try:
            severity = SeverityLevel(data["severity"])
        except ValueError as exc:
            valid = ", ".join(level.value for level in SeverityLevel)
            raise ValueError(
                f"Invalid severity '{data['severity']}'. Must be one of: {valid}"
            ) from exc

        alert_id = str(data["alert_id"]).strip()
        if not alert_id:
            raise ValueError("alert_id must be a non-empty string")

        source = str(data["source"]).strip()
        if not source:
            raise ValueError("source must be a non-empty string")

        message = str(data["message"]).strip()
        if not message:
            raise ValueError("message must be a non-empty string")

        correlation_id = str(data["correlation_id"]).strip()
        if not correlation_id:
            raise ValueError("correlation_id must be a non-empty string")

        persistence_count = int(data.get("persistence_count", 1))
        if persistence_count < 1:
            raise ValueError("persistence_count must be at least 1")

        cooldown_seconds = int(data.get("cooldown_seconds", 300))
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")

        payload = data.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dictionary")

        payload_with_meta = {
            **payload,
            "timestamp": time.time(),
            "submission_type": data.get("submission_type", "external"),
        }

        return cls(
            alert_id=alert_id,
            rule_id=None,
            source=source,
            severity=severity,
            message=message,
            correlation_id=correlation_id,
            payload=payload_with_meta,
            persistence_count=persistence_count,
            cooldown_seconds=cooldown_seconds,
        )
