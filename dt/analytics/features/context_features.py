"""Longer-context features built from hourly aggregate readings."""

import math
from statistics import mean

from dt.analytics.features.base import ExtractionContext, FeatureProvider
from dt.communication.dataclasses import AggregatedReading
from dt.communication.topics import Topics

_RAW_DRY_THRESHOLD = 400.0


def build_context_features(
    longer_context_aggregates: list[AggregatedReading],
) -> dict[str, float | None]:
    """Compatibility shim for old feature building logic."""
    context = ExtractionContext(
        reference_timestamp=0.0,
        longer_context_aggregates=longer_context_aggregates,
    )
    features: dict[str, float | None] = {}
    for provider in get_context_providers():
        features.update(provider.compute(context))
    return features


class LightExposureProvider(FeatureProvider):
    def __init__(self):
        super().__init__("context.light_exposure_proxy_24h")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        aggregates = context.aggregates_by_topic.get(Topics.LIGHT_INTENSITY, [])
        values = [aggregate.mean_value for aggregate in aggregates]
        return {"context.light_exposure_proxy_24h": mean(values) if values else None}


class VPDProvider(FeatureProvider):
    def __init__(self):
        super().__init__("context.vpd_kpa_24h")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        vpd_values = []
        # Iterate through each time bucket
        for bucket_aggregates in context.aggregates_by_bucket.values():
            # Create a mapping of topic to mean value for the current bucket (check if both temperature and humidity are present)
            bucket_data = {aggregate.topic: aggregate.mean_value for aggregate in bucket_aggregates}
            # Calculate VPD for the bucket if both temperature and humidity are available
            temp = bucket_data.get(Topics.TEMPERATURE)
            hum = bucket_data.get(Topics.HUMIDITY)
            if temp is not None and hum is not None:
                vpd_values.append(self._calculate_vpd(temp, hum))

        return {"context.vpd_kpa_24h": mean(vpd_values) if vpd_values else None}

    def _calculate_vpd(self, temp_c: float, humidity_pct: float) -> float:
        es = 0.61078 * math.exp(17.27 * temp_c / (temp_c + 237.3))
        ea = es * (humidity_pct / 100.0)
        return es - ea


class SoilMoistureDropProvider(FeatureProvider):
    def __init__(self):
        super().__init__("context.soil_moisture_drop_rate_24h")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        moisture_aggregates = context.aggregates_by_topic.get(Topics.SOIL_MOISTURE, [])
        if len(moisture_aggregates) >= 2:
            first = moisture_aggregates[0]
            last = moisture_aggregates[-1]
            hours = (last.bucket - first.bucket) / 3600.0
            if hours > 0:
                return {
                    "context.soil_moisture_drop_rate_24h": (first.mean_value - last.mean_value)
                    / hours
                }
        return {"context.soil_moisture_drop_rate_24h": None}


class LongDeltaProvider(FeatureProvider):
    def __init__(self, topic: Topics, feature_name: str):
        super().__init__(feature_name)
        self._topic = topic
        self._feature_name = feature_name

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        aggregates = context.aggregates_by_topic.get(self._topic, [])
        if len(aggregates) < 2:
            return {self._feature_name: None}

        return {self._feature_name: aggregates[-1].mean_value - aggregates[0].mean_value}


class SoilMoisturePersistenceProvider(FeatureProvider):
    def __init__(self):
        super().__init__("context.raw_dry_threshold_persistence_24h")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        raw_values = [
            a.avg_raw_value
            for a in context.aggregates_by_topic.get(Topics.SOIL_MOISTURE, [])
            if a.avg_raw_value is not None
        ]
        if not raw_values:
            return {"context.raw_dry_threshold_persistence_24h": None}
        dry_count = sum(1 for value in raw_values if value <= _RAW_DRY_THRESHOLD)
        return {"context.raw_dry_threshold_persistence_24h": dry_count / len(raw_values)}


def get_context_providers() -> list[FeatureProvider]:
    """Return providers for all context features."""
    return [
        LightExposureProvider(),
        VPDProvider(),
        SoilMoistureDropProvider(),
        LongDeltaProvider(Topics.LEAF_COUNT, "context.leaf_count_delta_24h"),
        LongDeltaProvider(Topics.PLANT_HEIGHT, "context.plant_height_delta_24h"),
        SoilMoisturePersistenceProvider(),
    ]
