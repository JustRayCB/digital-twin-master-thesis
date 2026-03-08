"""Utilities for manual UI smoke testing.

The dashboard UI is driven by Socket.IO events. In normal operation those
events originate from Kafka consumers (processed sensor readings and alerts).

This module generates synthetic payloads and emits them through the same Socket.IO
event names the frontend subscribes to, so the UI can be validated without Kafka.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass
from threading import Event

from flask_socketio import SocketIO

from dt.communication.topics import Topics


@dataclass(frozen=True)
class DemoConfig:
    """Configuration for the demo emitter."""

    plant_id: int = 1
    interval_seconds: float = 1.0


def build_demo_processed_payload(
    *,
    plant_id: int,
    sensor_id: int,
    unit: str,
    time_ms: int,
    value: float,
    raw_value: float | None,
    calibrated_value: float | None,
    normalized_value: float | None,
    dq_score: float,
    flags: dict[str, bool],
    correlation_id: str,
    calibration_profile_id: str | None,
    normalization_profile_id: str | None,
    imputed: bool = False,
) -> dict:
    """Build a ProcessedSensorData-shaped payload for the browser.

    The backend uses snake_case keys and a `time` field in milliseconds.
    """
    return {
        "plant_id": int(plant_id),
        "sensor_id": int(sensor_id),
        "time": int(time_ms),
        "unit": str(unit),
        "value": float(value),
        "raw_value": raw_value if raw_value is None else float(raw_value),
        "calibrated_value": calibrated_value if calibrated_value is None else float(calibrated_value),
        "normalized_value": normalized_value if normalized_value is None else float(normalized_value),
        "dq_score": float(dq_score),
        "imputed": bool(imputed),
        "flags": {str(k): bool(v) for k, v in dict(flags).items()},
        "correlation_id": str(correlation_id),
        "calibration_profile_id": (
            None if calibration_profile_id is None else str(calibration_profile_id)
        ),
        "normalization_profile_id": (
            None if normalization_profile_id is None else str(normalization_profile_id)
        ),
    }


def build_demo_alert_payload(
    *,
    plant_id: int,
    alert_key: str,
    time_ms: int,
    status: str,
    severity: str,
    message: str,
    correlation_id: str,
    acknowledged_by: str | None,
    acknowledged_ts: float | None,
    cleared_ts: float | None,
) -> dict:
    """Build an AlertHistoryEvent-shaped payload for the browser."""
    return {
        "alert_id": f"{int(plant_id)}:{str(alert_key)}",
        "alert_key": str(alert_key),
        "plant_id": int(plant_id),
        "time": int(time_ms),
        "status": str(status),
        "severity": str(severity),
        "message": str(message),
        "correlation_id": str(correlation_id),
        "acknowledged_by": acknowledged_by,
        "acknowledged_ts": acknowledged_ts,
        "cleared_ts": cleared_ts,
    }


def start_demo_emitter(socketio: SocketIO, config: DemoConfig) -> Event:
    """Start a background emitter that streams synthetic readings and alerts.

    Returns an Event that can be set to request a stop.
    """
    stop_event = Event()

    socketio.start_background_task(_run_demo_loop, socketio, config, stop_event)
    return stop_event


def _run_demo_loop(socketio: SocketIO, config: DemoConfig, stop_event: Event) -> None:
    """Emit synthetic sensor readings and alerts until stop_event is set."""
    sensor_topics = [
        Topics.TEMPERATURE,
        Topics.HUMIDITY,
        Topics.SOIL_MOISTURE,
        Topics.LIGHT_INTENSITY,
    ]
    sensor_units = {
        Topics.TEMPERATURE: "C",
        Topics.HUMIDITY: "%",
        Topics.SOIL_MOISTURE: "%",
        Topics.LIGHT_INTENSITY: "lux",
    }

    start = time.time()
    next_alert_at = start + 8.0
    alert_active = False

    while not stop_event.is_set():
        now = time.time()
        now_ms = int(now * 1000)

        for index, topic in enumerate(sensor_topics, start=1):
            phase = (now - start) / 10.0
            base = 0.0

            if topic == Topics.TEMPERATURE:
                base = 22.0 + 2.0 * math.sin(phase)
            elif topic == Topics.HUMIDITY:
                base = 45.0 + 10.0 * math.sin(phase + 1.3)
            elif topic == Topics.SOIL_MOISTURE:
                base = 30.0 + 5.0 * math.sin(phase + 2.1)
            elif topic == Topics.LIGHT_INTENSITY:
                base = 800.0 + 200.0 * math.sin(phase + 0.7)

            # Raw value: what a physical sensor might read (includes a small wobble).
            raw_value = base + 0.15 * math.sin((now - start) * 3.0 + index)

            # Calibrated value: small scale + offset.
            calibrated_value = raw_value * 1.01 + 0.05

            # Processed value: simple smoothing to differ from raw/calibrated.
            processed_value = (0.9 * base) + (0.1 * calibrated_value)

            # Occasionally mark a point as imputed to exercise UI flags.
            imputed = False
            if int(now - start) % 30 == 0 and int((now - start) * 10) % 10 == 0:
                processed_value = processed_value + 0.8
                imputed = True
            normalized_value = None
            if topic == Topics.LIGHT_INTENSITY:
                # BH1750 reference range: 0–65,535 lux.
                normalized_value = max(0.0, min(1.0, calibrated_value / 65535.0))
            elif topic in (Topics.TEMPERATURE, Topics.HUMIDITY, Topics.SOIL_MOISTURE):
                normalized_value = max(0.0, min(1.0, calibrated_value / 100.0))

            dq_score = 0.5 + 0.5 * math.sin((now - start) / 6.0 + (index * 0.4))
            dq_score = max(0.0, min(1.0, dq_score))

            flags: dict[str, bool] = {"valid_data_point": True, "range_violation": False}
            if dq_score < 0.3:
                flags["range_violation"] = True
                flags["valid_data_point"] = False

            payload = build_demo_processed_payload(
                plant_id=config.plant_id,
                sensor_id=index,
                unit=sensor_units[topic],
                time_ms=now_ms,
                value=processed_value,
                raw_value=raw_value,
                calibrated_value=calibrated_value,
                normalized_value=normalized_value,
                dq_score=dq_score,
                flags=flags,
                correlation_id=f"demo-{uuid.uuid4().hex[:8]}",
                calibration_profile_id="demo-calibration",
                normalization_profile_id="demo-normalization",
                imputed=imputed,
            )
            socketio.emit(topic.processed, payload)

        if now >= next_alert_at:
            if not alert_active:
                alert_active = True
                next_alert_at = now + 6.0
                socketio.emit(
                    "alerts_update",
                    build_demo_alert_payload(
                        plant_id=config.plant_id,
                        alert_key="demo_soil_moisture_low",
                        time_ms=now_ms,
                        status="active",
                        severity="warning",
                        message="Demo alert: soil moisture below threshold",
                        correlation_id=f"demo-alert-{uuid.uuid4().hex[:8]}",
                        acknowledged_by=None,
                        acknowledged_ts=None,
                        cleared_ts=None,
                    ),
                )
            else:
                alert_active = False
                next_alert_at = now + 12.0
                socketio.emit("alerts_remove", f"{config.plant_id}:demo_soil_moisture_low")

        time.sleep(max(0.05, float(config.interval_seconds)))
