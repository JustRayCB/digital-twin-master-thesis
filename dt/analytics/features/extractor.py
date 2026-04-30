"""Feature extraction boundary."""

from dt.analytics.features.base import ExtractionContext, FeatureSet
from dt.analytics.features.baseline import get_baseline_providers
from dt.analytics.features.context_features import get_context_providers
from dt.analytics.features.quality_features import get_quality_providers
from dt.analytics.features.schema import FEATURE_SCHEMA
from dt.communication.dataclasses import AggregatedReading, ProcessedSensorData


class FeatureExtractor:
    """Create deterministic model-ready features from processed telemetry."""

    def __init__(self):
        self._providers = [
            *get_baseline_providers(),
            *get_context_providers(),
            *get_quality_providers(),
        ]

    def extract(
        self,
        recent_readings_snapshot: list[ProcessedSensorData],
        reference_timestamp: float,
        longer_context_aggregates: list[AggregatedReading] | None = None,
    ) -> FeatureSet:
        context = ExtractionContext(
            reference_timestamp=float(reference_timestamp),
            recent_readings=recent_readings_snapshot,
            longer_context_aggregates=longer_context_aggregates or [],
        )

        all_features: dict[str, float | None] = {}
        for provider in self._providers:
            computed_features = provider.compute(context)
            undeclared_features = set(computed_features) - set(provider.feature_names)
            if undeclared_features:
                raise ValueError(
                    f"{provider.__class__.__name__} returned undeclared features: "
                    f"{sorted(undeclared_features)}"
                )
            all_features.update(computed_features)

        # Coverage Ratio depends on other features being computed
        all_features["quality.coverage_ratio"] = self._compute_coverage(all_features)

        # Confidence calculation
        confidence = self._calculate_confidence(all_features)

        ordered_features = {
            feature_name: all_features.get(feature_name)
            for feature_name in FEATURE_SCHEMA
        }

        return FeatureSet(
            reference_timestamp=context.reference_timestamp,
            features=ordered_features,
            confidence=confidence,
        )

    def _compute_coverage(self, computed_features: dict[str, float | None]) -> float:
        # Exclude quality features from coverage calculation to avoid bias
        non_quality_features = [
            v for k, v in computed_features.items() if not k.startswith("quality.")
        ]
        observed_count = sum(1 for value in non_quality_features if value is not None)
        return (
            observed_count / len(non_quality_features) if non_quality_features else 0.0
        )

    def _calculate_confidence(self, all_features: dict[str, float | None]) -> float:
        dq_confidence = all_features.get("quality.window_dq_mean", 0.0)
        coverage = all_features.get("quality.coverage_ratio", 0.0)
        freshness = all_features.get("quality.freshness_ratio", 0.0)
        imputation = all_features.get("quality.imputation_burden", 1.0)

        # Ensure we treat None as default values that don't zero out confidence if not intended,
        # but here we want zero if they are missing or bad.
        return max(
            0.0,
            min(
                1.0,
                float(dq_confidence if dq_confidence is not None else 0.0)
                * float(coverage if coverage is not None else 0.0)
                * float(freshness if freshness is not None else 0.0)
                * (1.0 - float(imputation if imputation is not None else 1.0)),
            ),
        )
