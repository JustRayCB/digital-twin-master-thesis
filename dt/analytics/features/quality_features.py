"""Quality and data-governance features."""

from statistics import mean
from dt.analytics.features.base import ExtractionContext, FeatureProvider


class ReadingCountProvider(FeatureProvider):
    def __init__(self):
        super().__init__("quality.recent_reading_count")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        return {"quality.recent_reading_count": float(len(context.recent_readings))}


class BucketCountProvider(FeatureProvider):
    def __init__(self):
        super().__init__("quality.longer_context_bucket_count")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        return {
            "quality.longer_context_bucket_count": float(
                len(context.longer_context_aggregates)
            )
        }


class CoverageRatioProvider(FeatureProvider):
    def __init__(self):
        super().__init__("quality.coverage_ratio")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        # Note: This usually requires knowledge of all other features computed.
        # We'll see how to handle this in the extractor or if we need a context update.
        return {"quality.coverage_ratio": None}


class WindowDQMeanProvider(FeatureProvider):
    def __init__(self):
        super().__init__("quality.window_dq_mean")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        dq_values = [r.dq_score for r in context.recent_readings]
        return {"quality.window_dq_mean": mean(dq_values) if dq_values else 0.0}


class FreshnessRatioProvider(FeatureProvider):
    def __init__(self):
        super().__init__("quality.freshness_ratio")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        if not context.recent_readings:
            return {"quality.freshness_ratio": 0.0}

        freshest_timestamp = max(r.timestamp for r in context.recent_readings)
        freshness_horizon_seconds = 900.0

        return {
            "quality.freshness_ratio": max(
                0.0,
                min(
                    1.0,
                    1.0
                    - (
                        max(
                            0.0, float(context.reference_timestamp) - freshest_timestamp
                        )
                        / freshness_horizon_seconds
                    ),
                ),
            )
        }


class ImputationBurdenProvider(FeatureProvider):
    def __init__(self):
        super().__init__("quality.imputation_burden")

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        if not context.recent_readings:
            return {"quality.imputation_burden": 1.0}
        return {
            "quality.imputation_burden": mean(
                1.0 if r.imputed else 0.0 for r in context.recent_readings
            )
        }


def get_quality_providers() -> list[FeatureProvider]:
    """Return providers for quality features."""
    return [
        ReadingCountProvider(),
        BucketCountProvider(),
        WindowDQMeanProvider(),
        FreshnessRatioProvider(),
        ImputationBurdenProvider(),
        # CoverageRatioProvider(), # Depends on other features, handling in extractor for now
    ]
