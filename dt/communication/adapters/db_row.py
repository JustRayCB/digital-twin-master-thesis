"""Database row adapter for PostgreSQL/TimescaleDB conversions.

Handles conversions specific to database storage:
- Topics enum ↔ short_name string (e.g., TEMPERATURE ↔ "temp")
- dict[ValidationFlag, bool] ↔ pipe-separated string (e.g., "range=true|roc=false")
- datetime ↔ Unix timestamp (seconds)

Uses generic adapter for base serialization, then applies DB-specific transformations.
"""

import json
from base64 import b64encode
from dataclasses import fields
from datetime import datetime
from typing import Any, TypeVar, Union

from typing_extensions import override

from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition, AlertHistoryEvent, ExternalAlertEvent, SensorAlertEvent)
from dt.communication.dataclasses.camera_snapshot import CameraSnapshot
from dt.communication.dataclasses.controller import (ActionCommand,
                                                     ControlMode, Routine,
                                                     RoutineUpdate)
from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData, ValidationFlag)
from dt.communication.dataclasses.sensor import SensorDescriptor
from dt.communication.topics import Topics

from .base import SerializationAdapter
from .generic import GenericAdapter

T = TypeVar("T")


# WARNING: DEPRECATED - NOT USED ANYMORE NEED TO REMOVE IT
class DbRowAdapter(SerializationAdapter):
    """Adapter for converting objects to/from database rows.

    Handles DB-specific transformations:
    - topic enum ↔ short_name string
    - flags dict ↔ pipe-separated string
    - datetime ↔ Unix timestamp

    Supports:
    - ProcessedSensorData: single dict for sensor_readings table
    - AggregatedReading: single dict for aggregates
    - SensorDescriptor: single dict for sensors table
    - AlertDefinition: single dict for alert_definitions table
    - AlertHistoryEvent: single dict for alert_history table
    - SensorAlertEvent: dict with 'history' and 'sensor' keys for alert_history + alert_sensors tables
    - ExternalAlertEvent: dict with 'history' and 'external' keys for alert_history + alert_external tables
    """

    def __init__(self) -> None:
        """Initialize with a GenericAdapter instance."""
        self._generic = GenericAdapter()

    @override
    def dump(self, obj: Any) -> dict[str, Any]:
        """Serialize object to database row dict(s).

        For alert events, returns structured dicts ready for multi-table inserts:
        - SensorAlertEvent: {"history": {...}, "sensor": {...}}
        - ExternalAlertEvent: {"history": {...}, "external": {...}}

        For other objects, returns single dict with DB-specific transformations applied.

        Parameters
        ----------
        obj : Any
            Object to serialize.

        Returns
        -------
        dict[str, Any]
            Dictionary (or structured dict) suitable for database insertion.
        """
        # Get base dict from generic adapter (enums already converted to strings)
        data = self._generic.dump(obj)

        # Apply DB-specific transformations
        if isinstance(obj, ProcessedSensorData):
            data["topic"] = obj.topic.short_name
            data["flags"] = self._flags_to_string(obj.flags)

        elif isinstance(obj, CameraSnapshot):
            data["topic"] = obj.topic.short_name

        elif isinstance(obj, AlertDefinition):
            # Flat dict for alert_definitions table
            pass  # Already flat from generic adapter

        elif isinstance(obj, SensorAlertEvent):
            # Extract history fields (AlertHistoryEvent base fields)
            history_fields = [f.name for f in fields(AlertHistoryEvent)]
            history_data = {k: data[k] for k in history_fields}

            # Apply DB-specific transformations to reading
            reading_data = self.dump(obj.reading)  # Reuse dump for ProcessedSensorData

            # Combine reading with threshold context fields for alert_sensors table
            sensor_data = {
                **reading_data,
                "threshold_op": data.get("threshold_op"),
                "threshold_value": data.get("threshold_value"),
                "range_min": data.get("range_min"),
                "range_max": data.get("range_max"),
            }

            return {"history": history_data, "sensor": sensor_data}

        elif isinstance(obj, ExternalAlertEvent):
            # Extract history fields (AlertHistoryEvent base fields)
            history_fields = [f.name for f in fields(AlertHistoryEvent)]
            history_data = {k: data[k] for k in history_fields}

            # Extract metadata for alert_external table
            external_data = {
                "plant_id": data["plant_id"],
                "metadata": data["metadata"],  # JSONB
            }

            return {"history": history_data, "external": external_data}

        elif isinstance(obj, AlertHistoryEvent):
            # Flat dict for alert_history table
            pass  # Already correct from generic adapter

        elif isinstance(obj, Routine | RoutineUpdate):
            data = self._dump_routine_payload(data)

        elif isinstance(obj, ControlMode):
            updated_at = data.get("updated_at")
            if isinstance(updated_at, str):
                try:
                    data["updated_at"] = datetime.fromisoformat(updated_at)
                except ValueError:
                    pass

        elif isinstance(obj, ActionCommand):
            pass

        return data

    @override
    def load(self, cls: type[T], row: Union[Any, tuple[Any, Any]]) -> T:
        """Deserialize database row(s) to object.

        For alert events that span multiple tables, pass tuple of rows:
        - SensorAlertEvent: (history_row, sensor_row)
        - ExternalAlertEvent: (history_row, external_row)

        Parameters
        ----------
        cls : type[T]
            Target class to deserialize into.
        row : NamedTuple or tuple[NamedTuple, NamedTuple]
            Database row(s) from query result.

        Returns
        -------
        T
            Deserialized object instance.
        """
        # Handle multi-row loads for alert events
        if cls == SensorAlertEvent:
            # Must be a plain tuple of 2 rows (not a NamedTuple/Row with 2 fields)
            if not (type(row) is tuple and len(row) == 2):
                raise ValueError("SensorAlertEvent requires (history_row, sensor_row) tuple")
            return self._load_sensor_alert_event(row[0], row[1])  # type: ignore

        elif cls == ExternalAlertEvent:
            if not (type(row) is tuple and len(row) == 2):
                raise ValueError("ExternalAlertEvent requires (history_row, external_row) tuple")
            return self._load_external_alert_event(row[0], row[1])  # type: ignore

        # For non-alert events, reject plain tuples (not NamedTuples/Row)
        if type(row) is tuple:
            raise ValueError(f"{cls.__name__} requires a single row, not a tuple of rows")

        # Single-row loads
        row_dict = row._asdict()  # type: ignore

        # Apply DB-specific reverse transformations
        if cls == ProcessedSensorData:
            row_dict["flags"] = self._string_to_flags(row_dict.get("flags"))
            row_dict["topic"] = Topics.from_short_name(row_dict.get("topic"))
            row_dict["timestamp"] = self._to_unix_timestamp(row_dict.get("timestamp"))

        elif cls == CameraSnapshot:
            row_dict["timestamp"] = self._to_unix_timestamp(row_dict.get("timestamp"))
            topic_value = row_dict.get("topic")
            if topic_value is not None:
                topic_text = str(topic_value)
                row_dict["topic"] = Topics.from_short_name(topic_text)
            image_bytes = row_dict.pop("image", None)
            if image_bytes is not None:
                row_dict["image"] = b64encode(bytes(image_bytes)).decode("ascii")

        elif cls == AggregatedReading:
            row_dict["bucket"] = self._to_unix_timestamp(row_dict.get("bucket"))
            row_dict["topic"] = Topics.from_short_name(row_dict["topic"])

        elif cls == AlertDefinition:
            pass  # No transformations needed

        elif cls == AlertHistoryEvent:
            row_dict["timestamp"] = self._to_unix_timestamp(row_dict.get("timestamp"))
            row_dict["acknowledged_ts"] = self._to_unix_timestamp(row_dict.get("acknowledged_ts"))
            row_dict["cleared_ts"] = self._to_unix_timestamp(row_dict.get("cleared_ts"))

        elif cls == Routine:
            graph_payload = row_dict.pop("graph", None)
            compiled_payload = row_dict.get("compiled_rules")
            if isinstance(compiled_payload, str):
                try:
                    compiled_payload = json.loads(compiled_payload)
                except json.JSONDecodeError:
                    compiled_payload = None
            row_dict["graph"] = graph_payload
            row_dict["compiled_rules"] = compiled_payload

            created_at = row_dict.get("created_at")
            if isinstance(created_at, datetime):
                row_dict["created_at"] = created_at.isoformat()
            updated_at = row_dict.get("updated_at")
            if isinstance(updated_at, datetime):
                row_dict["updated_at"] = updated_at.isoformat()

        elif cls == ActionCommand:
            row_dict["event_at"] = self._to_unix_timestamp(row_dict.get("event_at"))

        elif cls == ControlMode:
            updated_at = row_dict.get("updated_at")
            if isinstance(updated_at, datetime):
                row_dict["updated_at"] = updated_at.isoformat()
            elif isinstance(updated_at, str):
                try:
                    row_dict["updated_at"] = datetime.fromisoformat(updated_at).isoformat()
                except ValueError:
                    pass

        elif cls == SensorDescriptor:
            pass  # No transformations needed

        # Use generic adapter to construct the object
        return self._generic.load(cls, row_dict)

    def _dump_routine_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        graph_payload = data.pop("graph", None)
        if graph_payload is not None:
            data["graph"] = json.dumps(graph_payload)

        compiled_payload = data.get("compiled_rules")
        if compiled_payload is not None:
            if isinstance(compiled_payload, str):
                try:
                    compiled_payload = json.loads(compiled_payload)
                except json.JSONDecodeError as exc:
                    raise ValueError("compiled_rules must be valid JSON") from exc
            data["compiled_rules"] = json.dumps(compiled_payload)

        return data

    def _load_sensor_alert_event(self, history_row: Any, sensor_row: Any) -> SensorAlertEvent:
        """Load SensorAlertEvent from history and sensor snapshot rows.

        Parameters
        ----------
        history_row : NamedTuple
            Row from alert_history table.
        sensor_row : NamedTuple
            Row from alert_sensors table.

        Returns
        -------
        SensorAlertEvent
            Combined alert event with reading.
        """
        history_dict = history_row._asdict()
        sensor_dict = sensor_row._asdict()

        # Convert timestamp if needed
        history_dict["timestamp"] = self._to_unix_timestamp(history_dict.get("timestamp"))
        history_dict["acknowledged_ts"] = self._to_unix_timestamp(
            history_dict.get("acknowledged_ts")
        )
        history_dict["cleared_ts"] = self._to_unix_timestamp(history_dict.get("cleared_ts"))

        # Load AlertHistoryEvent using generic adapter for type coercion (string → enum)
        history_event = self._generic.load(AlertHistoryEvent, history_dict)

        # Reconstruct ProcessedSensorData from sensor snapshot
        reading = ProcessedSensorData(
            plant_id=sensor_dict["plant_id"],
            sensor_id=sensor_dict["sensor_id"],
            timestamp=self._to_unix_timestamp(sensor_dict.get("timestamp")),
            value=sensor_dict["value"],
            unit=sensor_dict["unit"],
            topic=Topics.from_short_name(sensor_dict["topic"]),
            correlation_id=sensor_dict["correlation_id"],
            flags=self._string_to_flags(sensor_dict.get("flags")),
            dq_score=sensor_dict["dq_score"],
            imputed=sensor_dict["imputed"],
            raw_value=sensor_dict.get("raw_value"),
            calibrated_value=sensor_dict.get("calibrated_value"),
            normalized_value=sensor_dict.get("normalized_value"),
            calibration_profile_id=sensor_dict.get("calibration_profile_id"),
            normalization_profile_id=sensor_dict.get("normalization_profile_id"),
        )

        # Construct SensorAlertEvent from history event + reading + threshold fields
        return SensorAlertEvent(
            alert_key=history_event.alert_key,
            plant_id=history_event.plant_id,
            timestamp=history_event.timestamp,
            status=history_event.status,
            severity=history_event.severity,
            message=history_event.message,
            correlation_id=history_event.correlation_id,
            acknowledged_by=history_event.acknowledged_by,
            acknowledged_ts=history_event.acknowledged_ts,
            cleared_ts=history_event.cleared_ts,
            reading=reading,
            threshold_op=sensor_dict.get("threshold_op"),
            threshold_value=sensor_dict.get("threshold_value"),
            range_min=sensor_dict.get("range_min"),
            range_max=sensor_dict.get("range_max"),
        )

    def _load_external_alert_event(self, history_row: Any, external_row: Any) -> ExternalAlertEvent:
        """Load ExternalAlertEvent from history and external metadata rows.

        Parameters
        ----------
        history_row : NamedTuple
            Row from alert_history table.
        external_row : NamedTuple
            Row from alert_external table.

        Returns
        -------
        ExternalAlertEvent
            Combined alert event with metadata.
        """
        history_dict = history_row._asdict()
        external_dict = external_row._asdict()

        # Convert timestamp if needed
        history_dict["timestamp"] = self._to_unix_timestamp(history_dict.get("timestamp"))
        history_dict["acknowledged_ts"] = self._to_unix_timestamp(
            history_dict.get("acknowledged_ts")
        )
        history_dict["cleared_ts"] = self._to_unix_timestamp(history_dict.get("cleared_ts"))

        # Load AlertHistoryEvent using generic adapter for type coercion (string → enum)
        history_event = self._generic.load(AlertHistoryEvent, history_dict)

        return ExternalAlertEvent(
            alert_key=history_event.alert_key,
            plant_id=history_event.plant_id,
            timestamp=history_event.timestamp,
            status=history_event.status,
            severity=history_event.severity,
            message=history_event.message,
            correlation_id=history_event.correlation_id,
            acknowledged_by=history_event.acknowledged_by,
            acknowledged_ts=history_event.acknowledged_ts,
            cleared_ts=history_event.cleared_ts,
            metadata=external_dict["metadata"],
        )

    def _to_unix_timestamp(self, value: Any) -> Any:
        """Convert database datetime to Unix timestamp float.

        Handles None for nullable columns.
        """
        return value.timestamp() if value is not None else None

    def _flags_to_string(self, flags: dict[ValidationFlag, bool]) -> str:
        """Convert flags dict to pipe-separated string.

        Parameters
        ----------
        flags : dict[ValidationFlag, bool]
            Validation flags dictionary.

        Returns
        -------
        str
            Pipe-separated string like "range=true|roc=false|stuck=true".
        """
        return "|".join(f"{flag.value}={str(value).lower()}" for flag, value in flags.items())

    def _string_to_flags(self, flags_text: str) -> dict[ValidationFlag, bool]:
        """Parse flags from pipe-separated string.

        Parameters
        ----------
        flags_text : str
            Pipe-separated flags string.

        Returns
        -------
        dict[ValidationFlag, bool]
            Parsed flags dictionary.
        """
        flags: dict[ValidationFlag, bool] = {}
        if not flags_text:
            return flags

        for flag_pair in flags_text.split("|"):
            try:
                flag_name, flag_value_str = flag_pair.split("=")
                flags[ValidationFlag(flag_name)] = flag_value_str.lower() == "true"
            except (ValueError, KeyError):
                # Skip malformed flag pairs
                self.logger.warning(f"Malformed flag pair: {flag_pair}")
                continue

        return flags
