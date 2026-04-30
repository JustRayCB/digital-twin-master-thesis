"""Baseline features built from already-bounded readings or aggregates."""

import math
from statistics import mean, median, pstdev

import numpy as np

from dt.analytics.features.base import ExtractionContext, FeatureProvider
from dt.analytics.features.schema import BASELINE_METRICS, BASELINE_TOPICS
from dt.communication.dataclasses import AggregatedReading, ProcessedSensorData
from dt.communication.topics import Topics


def build_baseline_features(
    readings_or_aggregates: list[ProcessedSensorData] | list[AggregatedReading],
) -> dict[str, float | None]:
    """Compatibility shim for old feature building logic."""
    recent_readings: list[ProcessedSensorData] = []
    longer_context_aggregates: list[AggregatedReading] = []
    for item in readings_or_aggregates:
        if isinstance(item, ProcessedSensorData):
            recent_readings.append(item)
        elif isinstance(item, AggregatedReading):
            longer_context_aggregates.append(item)

    context = ExtractionContext(
        reference_timestamp=0.0,
        recent_readings=recent_readings,
        longer_context_aggregates=longer_context_aggregates,
    )
    features: dict[str, float | None] = {}
    for provider in get_baseline_providers():
        features.update(provider.compute(context))
    return features


class BaselineTopicProvider(FeatureProvider):
    """General provider for topic-based baseline metrics."""

    def __init__(self, topic: Topics):
        self._prefix = topic.short_name
        super().__init__(*(f"{self._prefix}.{metric}" for metric in BASELINE_METRICS))
        self._topic = topic

    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        readings = context.recent_readings_by_topic.get(self._topic, [])
        if readings:
            return _features_from_readings(self._prefix, readings)

        aggregates = context.aggregates_by_topic.get(self._topic, [])
        if aggregates:
            return _features_from_aggregates(self._prefix, aggregates)

        return _empty_topic_features(self._prefix)


def _features_from_readings(
    prefix: str,
    readings: list[ProcessedSensorData],
) -> dict[str, float | None]:
    values = [item.value for item in readings]
    dq_scores = [item.dq_score for item in readings]
    imputed_flags = [1.0 if item.imputed else 0.0 for item in readings]
    minimum = min(values) if values else None
    maximum = max(values) if values else None

    delta = values[-1] - values[0] if len(values) >= 2 else None

    skewness = None
    kurtosis = None
    if len(values) >= 3:
        # Fisher skewness and kurtosis
        v_arr = np.array(values)
        v_mean = np.mean(v_arr)
        v_std = np.std(v_arr)
        if v_std > 0:
            skewness = float(np.mean((v_arr - v_mean) ** 3) / (v_std**3))
            kurtosis = float(np.mean((v_arr - v_mean) ** 4) / (v_std**4))

    mm_ratio = None
    v_median = median(values) if values else None
    v_mean = mean(values) if values else None
    if v_median is not None and v_median != 0 and v_mean is not None:
        mm_ratio = v_mean / v_median

    delta_std = None
    if len(values) >= 2:
        # Step changes between readings
        deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
        delta_std = pstdev(deltas)

    return {
        f"{prefix}.count": float(len(values)),
        f"{prefix}.mean": v_mean,
        f"{prefix}.last": values[-1] if values else None,
        f"{prefix}.std": pstdev(values) if values else None,
        f"{prefix}.min": minimum,
        f"{prefix}.max": maximum,
        f"{prefix}.range": (
            (maximum - minimum) if minimum is not None and maximum is not None else None
        ),
        f"{prefix}.delta": delta,
        f"{prefix}.dq_mean": mean(dq_scores) if dq_scores else None,
        f"{prefix}.dq_min": min(dq_scores) if dq_scores else None,
        f"{prefix}.imputation_burden": mean(imputed_flags) if imputed_flags else None,
        f"{prefix}.skewness": skewness,
        f"{prefix}.kurtosis": kurtosis,
        f"{prefix}.mean_median_ratio": mm_ratio,
        f"{prefix}.delta_std": delta_std,
    }


def _features_from_aggregates(
    prefix: str,
    aggregates: list[AggregatedReading],
) -> dict[str, float | None]:
    if not aggregates:
        return _empty_topic_features(prefix)

    weighted_count = float(sum(item.sample_count for item in aggregates))
    weighted_mean = sum(item.mean_value * item.sample_count for item in aggregates) / weighted_count
    weighted_dq_mean = (
        sum(item.avg_dq_score * item.sample_count for item in aggregates) / weighted_count
    )
    weighted_imputation = sum(item.imputed_count for item in aggregates) / weighted_count
    minimum = min(item.min_value for item in aggregates)
    maximum = max(item.max_value for item in aggregates)

    # Historical trend features from bucket sequences
    last_val = aggregates[-1].mean_value
    delta_val = (
        aggregates[-1].mean_value - aggregates[0].mean_value if len(aggregates) >= 2 else 0.0
    )
    dq_min_val = min(item.avg_dq_score for item in aggregates)

    # Proxies for sequential/distributional features on aggregates
    mm_ratio = None
    all_means = [item.mean_value for item in aggregates]
    v_median = median(all_means) if all_means else None
    if v_median is not None and v_median != 0:
        mm_ratio = weighted_mean / v_median

    delta_std = None
    if len(aggregates) >= 2:
        # Measure stability of the hourly trend
        bucket_deltas = [all_means[i] - all_means[i - 1] for i in range(1, len(all_means))]
        delta_std = pstdev(bucket_deltas)

    # Note: For skewness and kurtosis, proper combination of moments would require
    # accessing the underlying value_stats object, which isn't currently passed here.
    # For now, we take the weighted average of the pre-computed hourly stats as a proxy,
    # or keep them None if high accuracy is required over 24h.
    weighted_skewness = None
    skew_vals = [item.skewness_value for item in aggregates if item.skewness_value is not None]
    if skew_vals:
        weighted_skewness = (
            sum(
                item.skewness_value * item.sample_count
                for item in aggregates
                if item.skewness_value is not None
            )
            / weighted_count
        )

    weighted_kurtosis = None
    kurt_vals = [item.kurtosis_value for item in aggregates if item.kurtosis_value is not None]
    if kurt_vals:
        weighted_kurtosis = (
            sum(
                item.kurtosis_value * item.sample_count
                for item in aggregates
                if item.kurtosis_value is not None
            )
            / weighted_count
        )

    std_value = None
    if weighted_count > 1:
        can_compute_std = True
        ss_within = 0.0
        ss_between = 0.0

        for item in aggregates:
            if item.sample_count > 1:
                if item.variance_value is None:
                    can_compute_std = False
                    break
                ss_within += item.variance_value * (item.sample_count - 1)

            ss_between += item.sample_count * ((item.mean_value - weighted_mean) ** 2)

        if can_compute_std:
            population_variance = (ss_within + ss_between) / weighted_count
            std_value = math.sqrt(population_variance)
    elif weighted_count == 1:
        std_value = 0.0

    return {
        f"{prefix}.count": weighted_count,
        f"{prefix}.mean": weighted_mean,
        f"{prefix}.last": last_val,
        f"{prefix}.std": std_value,
        f"{prefix}.min": minimum,
        f"{prefix}.max": maximum,
        f"{prefix}.range": maximum - minimum,
        f"{prefix}.delta": delta_val,
        f"{prefix}.dq_mean": weighted_dq_mean,
        f"{prefix}.dq_min": dq_min_val,
        f"{prefix}.imputation_burden": weighted_imputation,
        f"{prefix}.skewness": weighted_skewness,
        f"{prefix}.kurtosis": weighted_kurtosis,
        f"{prefix}.mean_median_ratio": mm_ratio,
        f"{prefix}.delta_std": delta_std,
    }


def _empty_topic_features(prefix: str) -> dict[str, float | None]:
    return {
        f"{prefix}.count": 0.0,
        f"{prefix}.mean": None,
        f"{prefix}.last": None,
        f"{prefix}.std": None,
        f"{prefix}.min": None,
        f"{prefix}.max": None,
        f"{prefix}.range": None,
        f"{prefix}.delta": None,
        f"{prefix}.dq_mean": None,
        f"{prefix}.dq_min": None,
        f"{prefix}.imputation_burden": None,
        f"{prefix}.skewness": None,
        f"{prefix}.kurtosis": None,
        f"{prefix}.mean_median_ratio": None,
        f"{prefix}.delta_std": None,
    }


def get_baseline_providers() -> list[FeatureProvider]:
    """Return providers for all baseline features."""
    return [BaselineTopicProvider(topic) for topic in BASELINE_TOPICS]
