"""Shared contracts for analytics feature extraction."""

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from dt.analytics.features.schema import FEATURE_SCHEMA
from dt.communication.dataclasses import AggregatedReading, ProcessedSensorData
from dt.communication.topics import Topics


@dataclass
class ExtractionContext:
    """Read-only context for feature providers."""

    reference_timestamp: float
    recent_readings: list[ProcessedSensorData] = field(default_factory=list)
    longer_context_aggregates: list[AggregatedReading] = field(default_factory=list)
    _recent_readings_by_topic: dict[Topics, list[ProcessedSensorData]] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _aggregates_by_topic: dict[Topics, list[AggregatedReading]] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _aggregates_by_bucket: dict[float, list[AggregatedReading]] | None = field(
        default=None,
        init=False,
        repr=False,
    )

    @property
    def recent_readings_by_topic(self) -> dict[Topics, list[ProcessedSensorData]]:
        """Recent readings grouped by topic and sorted by event time."""
        if self._recent_readings_by_topic is None:
            grouped: dict[Topics, list[ProcessedSensorData]] = defaultdict(list)
            for reading in self.recent_readings:
                grouped[reading.topic].append(reading)
            for topic_readings in grouped.values():
                topic_readings.sort(key=lambda item: (item.timestamp, item.sensor_id))
            self._recent_readings_by_topic = dict(grouped)
        return self._recent_readings_by_topic or {}

    @property
    def aggregates_by_topic(self) -> dict[Topics, list[AggregatedReading]]:
        """Longer-context aggregates grouped by topic and sorted by bucket."""
        if self._aggregates_by_topic is None:
            grouped: dict[Topics, list[AggregatedReading]] = defaultdict(list)
            for aggregate in self.longer_context_aggregates:
                grouped[aggregate.topic].append(aggregate)
            for topic_aggregates in grouped.values():
                topic_aggregates.sort(key=lambda item: item.bucket)
            self._aggregates_by_topic = dict(grouped)
        return self._aggregates_by_topic or {}

    @property
    def aggregates_by_bucket(self) -> dict[float, list[AggregatedReading]]:
        """Longer-context aggregates grouped by bucket timestamp."""
        if self._aggregates_by_bucket is None:
            grouped: dict[float, list[AggregatedReading]] = defaultdict(list)
            for aggregate in self.longer_context_aggregates:
                grouped[aggregate.bucket].append(aggregate)
            self._aggregates_by_bucket = dict(grouped)
        return self._aggregates_by_bucket or {}


class FeatureProvider(ABC):
    """Base for grouped feature extraction logic."""

    def __init__(self, *feature_names: str):
        if not feature_names:
            raise ValueError("Feature providers must declare at least one feature name.")
        for feature_name in feature_names:
            if feature_name not in FEATURE_SCHEMA:
                raise ValueError(f"Feature name '{feature_name}' is not in the schema.")
        self._feature_names = tuple(feature_names)

    @property
    def feature_names(self) -> tuple[str, ...]:
        """The feature names owned by this provider."""
        return self._feature_names

    @abstractmethod
    def compute(self, context: ExtractionContext) -> dict[str, float | None]:
        """Calculate the provider-owned features from context."""
        ...


@dataclass
class FeatureSet:
    """Container for deterministic model-ready features."""

    reference_timestamp: float
    features: dict[str, float | None]
    confidence: float

    def to_row(
        self,
        schema: Sequence[str] = FEATURE_SCHEMA,
    ) -> dict[str, float | None]:
        """Return one feature row in stable schema order."""
        return {feature_name: self.features.get(feature_name) for feature_name in schema}

    def to_dataframe(
        self,
        schema: Sequence[str] = FEATURE_SCHEMA,
    ):
        """Return one-row DataFrame with stable schema columns."""
        import pandas as pd

        return pd.DataFrame([self.to_row(schema=schema)], columns=list(schema))

    def to_ndarray(
        self,
        schema: Sequence[str] = FEATURE_SCHEMA,
    ):
        """Return one-row float matrix with NaN for missing values."""
        import numpy as np

        row = self.to_row(schema=schema)
        return np.asarray(
            [
                [
                    np.nan if row[feature_name] is None else float(row[feature_name])
                    for feature_name in schema
                ]
            ],
            dtype=float,
        )
