from __future__ import annotations

from base64 import b64encode
from typing import Any

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.db.base import DbSerializer
from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.camera_snapshot import CameraSnapshot
from dt.communication.dataclasses.processed_sensor_data import \
    ProcessedSensorData
from dt.communication.dataclasses.sensor import SensorDescriptor


@serializes(ProcessedSensorData, "db_row")
class ProcessedSensorDataDbSerializer(DbSerializer[ProcessedSensorData]):
    def dump(self, obj: ProcessedSensorData) -> dict[str, Any]:
        data = self._generic.dump(obj)
        data["topic"] = obj.topic.short_name
        data["flags"] = self._flags_to_string(obj.flags)
        return data

    def load(self, cls: type[ProcessedSensorData], data: Any) -> ProcessedSensorData:
        row_dict = data._asdict()
        row_dict["flags"] = self._string_to_flags(row_dict.get("flags"))
        row_dict["timestamp"] = self._to_unix(row_dict.get("timestamp"))
        return self._generic.load(cls, row_dict)


@serializes(AggregatedReading, "db_row")
class AggregatedReadingDbSerializer(DbSerializer[AggregatedReading]):
    def dump(self, obj: AggregatedReading) -> dict[str, Any]:
        data = self._generic.dump(obj)
        data["topic"] = obj.topic.short_name
        return data

    def load(self, cls: type[AggregatedReading], data: Any) -> AggregatedReading:
        row_dict = data._asdict()
        row_dict["bucket"] = self._to_unix(row_dict.get("bucket"))
        return self._generic.load(cls, row_dict)


@serializes(CameraSnapshot, "db_row")
class CameraSnapshotDbSerializer(DbSerializer[CameraSnapshot]):
    def dump(self, obj: CameraSnapshot) -> dict[str, Any]:
        data = self._generic.dump(obj)
        data["topic"] = obj.topic.short_name
        return data

    def load(self, cls: type[CameraSnapshot], data: Any) -> CameraSnapshot:
        row_dict = data._asdict()
        row_dict["timestamp"] = self._to_unix(row_dict.get("timestamp"))

        image_bytes = row_dict.pop("image", None)
        if image_bytes is not None:
            row_dict["image"] = b64encode(bytes(image_bytes)).decode("ascii")

        return self._generic.load(cls, row_dict)
