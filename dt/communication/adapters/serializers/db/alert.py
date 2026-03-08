from __future__ import annotations

from dataclasses import fields
from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.db.base import DbSerializer
from dt.communication.adapters.serializers.db.sensor import \
    ProcessedSensorDataDbSerializer
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition, AlertHistoryEvent, ExternalAlertEvent, SensorAlertEvent)
from dt.communication.dataclasses.processed_sensor_data import \
    ProcessedSensorData


@serializes(AlertHistoryEvent, "db_row")
class AlertHistoryEventDbSerializer(DbSerializer[AlertHistoryEvent]):
    def _dump_history_fields(self, obj: AlertHistoryEvent) -> dict[str, Any]:
        data = self._generic.dump(obj)
        history_fields = [field.name for field in fields(AlertHistoryEvent)]
        history_data = {key: data[key] for key in history_fields}
        history_data["timestamp"] = obj.timestamp
        history_data["acknowledged_ts"] = obj.acknowledged_ts
        history_data["cleared_ts"] = obj.cleared_ts
        return history_data

    def _load_history_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            **data,
            "timestamp": self._to_unix(data.get("timestamp")),
            "acknowledged_ts": self._to_unix(data.get("acknowledged_ts")),
            "cleared_ts": self._to_unix(data.get("cleared_ts")),
        }

    def dump(self, obj: AlertHistoryEvent) -> dict[str, Any]:
        return self._dump_history_fields(obj)

    def load(self, cls: type[AlertHistoryEvent], data: Any) -> AlertHistoryEvent:
        return self._generic.load(cls, self._load_history_dict(data._asdict()))


@serializes(SensorAlertEvent, "db_row")
class SensorAlertEventDbSerializer(AlertHistoryEventDbSerializer):
    def __init__(self) -> None:
        super().__init__()
        self._sensor_s = ProcessedSensorDataDbSerializer()

    def dump(self, obj: SensorAlertEvent) -> dict[str, Any]:
        return {
            "history": self._dump_history_fields(obj),
            "sensor": {
                **self._sensor_s.dump(obj.reading),
                "threshold_op": obj.threshold_op,
                "threshold_value": obj.threshold_value,
                "range_min": obj.range_min,
                "range_max": obj.range_max,
            },
        }

    def load(self, cls: type[SensorAlertEvent], data: Any) -> SensorAlertEvent:
        if not (type(data) is tuple and len(data) == 2):
            raise ValueError("SensorAlertEventDbSerializer.load requires (history_row, sensor_row)")

        history_dict = self._load_history_dict(data[0]._asdict())
        sensor_dict = data[1]._asdict()
        reading = self._sensor_s.load(ProcessedSensorData, data[1])

        return self._generic.load(
            cls,
            {
                **history_dict,
                "reading": self._generic.dump(
                    reading
                ),  # We first load to get the correct type conversion from the DB, then dump to get the dict representation for the constructor
                "threshold_op": sensor_dict.get("threshold_op"),
                "threshold_value": sensor_dict.get("threshold_value"),
                "range_min": sensor_dict.get("range_min"),
                "range_max": sensor_dict.get("range_max"),
            },
        )


@serializes(ExternalAlertEvent, "db_row")
class ExternalAlertEventDbSerializer(AlertHistoryEventDbSerializer):
    def dump(self, obj: ExternalAlertEvent) -> dict[str, Any]:
        return {
            "history": self._dump_history_fields(obj),
            "external": {
                "plant_id": obj.plant_id,
                "metadata": obj.metadata,
            },
        }

    def load(self, cls: type[ExternalAlertEvent], data: Any) -> ExternalAlertEvent:
        if not (type(data) is tuple and len(data) == 2):
            raise ValueError(
                "ExternalAlertEventDbSerializer.load requires (history_row, external_row)"
            )

        history_dict = self._load_history_dict(data[0]._asdict())
        external_dict = data[1]._asdict()

        return self._generic.load(
            cls,
            {
                **history_dict,
                "metadata": external_dict["metadata"],
            },
        )
