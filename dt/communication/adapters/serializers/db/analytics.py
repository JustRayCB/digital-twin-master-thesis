from __future__ import annotations

from typing import Any, TypeVar

from dt.communication.adapters.registry import serializes
from dt.communication.adapters.serializers.db.base import DbSerializer
from dt.communication.dataclasses.analytics import (
    ForecastResult,
    HealthAssessment,
    Recommendation,
)

T = TypeVar("T")


class AnalyticsDbSerializer(DbSerializer[T]):
    def _load_timestamp_value(self, row_dict: dict[str, Any], *field_names: str) -> Any:
        for field_name in field_names:
            if field_name in row_dict:
                return self._to_unix(row_dict.pop(field_name))
        return None


@serializes(HealthAssessment, "db_row")
class HealthAssessmentDbSerializer(AnalyticsDbSerializer[HealthAssessment]):
    def dump(self, obj: HealthAssessment) -> dict[str, Any]:
        data = self._generic.dump(obj)
        data["model_metadata"] = self._dump_json_value(data.get("model_metadata"))
        return data

    def load(self, cls: type[HealthAssessment], data: Any) -> HealthAssessment:
        row_dict = self._row_to_dict(data)
        row_dict["timestamp"] = self._load_timestamp_value(row_dict, "timestamp", "assessed_at")
        row_dict["model_metadata"] = self._load_json_value(row_dict.get("model_metadata"))
        return self._generic.load(cls, row_dict)


@serializes(ForecastResult, "db_row")
class ForecastResultDbSerializer(AnalyticsDbSerializer[ForecastResult]):
    def dump(self, obj: ForecastResult) -> dict[str, Any]:
        data = self._generic.dump(obj)
        data["features_used"] = self._dump_json_value(data.get("features_used"))
        data["inference_metadata"] = self._dump_json_value(data.get("inference_metadata"))
        data["model_metadata"] = self._dump_json_value(data.get("model_metadata"))
        return data

    def load(self, cls: type[ForecastResult], data: Any) -> ForecastResult:
        row_dict = self._row_to_dict(data)
        row_dict["timestamp"] = self._load_timestamp_value(row_dict, "timestamp", "forecast_at")
        row_dict["features_used"] = self._load_json_value(row_dict.get("features_used"))
        row_dict["inference_metadata"] = self._load_json_value(row_dict.get("inference_metadata"))
        row_dict["model_metadata"] = self._load_json_value(row_dict.get("model_metadata"))
        return self._generic.load(cls, row_dict)


@serializes(Recommendation, "db_row")
class RecommendationDbSerializer(AnalyticsDbSerializer[Recommendation]):
    def dump(self, obj: Recommendation) -> dict[str, Any]:
        data = self._generic.dump(obj)
        data["actions"] = self._dump_json_value(data.get("actions"))
        data["action_results"] = self._dump_json_value(data.get("action_results"))
        data["model_metadata"] = self._dump_json_value(data.get("model_metadata"))
        return data

    def load(self, cls: type[Recommendation], data: Any) -> Recommendation:
        row_dict = self._row_to_dict(data)
        row_dict["timestamp"] = self._load_timestamp_value(
            row_dict, "timestamp", "decided_at", "recommended_at"
        )
        row_dict["actions"] = self._load_json_value(row_dict.get("actions"))
        row_dict["action_results"] = self._load_json_value(row_dict.get("action_results"))
        row_dict["model_metadata"] = self._load_json_value(row_dict.get("model_metadata"))
        return self._generic.load(cls, row_dict)
