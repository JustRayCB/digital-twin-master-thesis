"""Explicit feature schema shared by online and offline paths."""

from dt.communication.topics import Topics

BASELINE_TOPICS: tuple[Topics, ...] = (
    Topics.TEMPERATURE,
    Topics.HUMIDITY,
    Topics.SOIL_MOISTURE,
    Topics.LIGHT_INTENSITY,
    Topics.GREEN_RATIO,
    Topics.LEAF_COUNT,
    Topics.PLANT_HEIGHT,
)

BASELINE_METRICS: tuple[str, ...] = (
    "count",
    "mean",
    "last",
    "std",
    "min",
    "max",
    "range",
    "delta",
    "dq_mean",
    "dq_min",
    "imputation_burden",
    "skewness",
    "kurtosis",
    "mean_median_ratio",
    "delta_std",
)

CONTEXT_FEATURE_NAMES: tuple[str, ...] = (
    "context.light_exposure_proxy_24h",
    "context.vpd_kpa_24h",
    "context.soil_moisture_drop_rate_24h",
    "context.leaf_count_delta_24h",
    "context.plant_height_delta_24h",
    "context.raw_dry_threshold_persistence_24h",
)

QUALITY_FEATURE_NAMES: tuple[str, ...] = (
    "quality.recent_reading_count",
    "quality.longer_context_bucket_count",
    "quality.coverage_ratio",
    "quality.window_dq_mean",
    "quality.freshness_ratio",
    "quality.imputation_burden",
)


def baseline_feature_names() -> tuple[str, ...]:
    """Return ordered baseline feature names."""
    return tuple(
        f"{topic.short_name}.{metric}"
        for topic in BASELINE_TOPICS
        for metric in BASELINE_METRICS
    )


FEATURE_SCHEMA: tuple[str, ...] = (
    *baseline_feature_names(),
    *CONTEXT_FEATURE_NAMES,
    *QUALITY_FEATURE_NAMES,
)
