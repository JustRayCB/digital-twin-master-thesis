"""Evaluate three-hour soil-moisture forecasts against persistence.

Usage:
    python scripts/evaluate_forecasts.py \
        docs/data/dtwin-data-2026-05-15T11-25-11-175Z.json.gz \
        --plot forecast-validation.png

For each forecast made at time t, persistence predicts that soil moisture at
t + 3 h will equal the measurement used at t. Both predictions are compared
with the first measurement at or after t + 3 h. Measurements delayed by more
than 5 minutes are excluded. Errors are observed value minus predicted value.
"""

from __future__ import annotations

import argparse
import gzip
import json
from bisect import bisect_left
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from statistics import mean
from typing import Any

SOIL_MOISTURE_TOPIC = "dt.sensors.soil_moisture"
DEFAULT_HORIZON_SECONDS = 3 * 60 * 60
DEFAULT_MAX_MATCH_DELAY_SECONDS = 5 * 60


@dataclass(frozen=True)
class ForecastMatch:
    """RLS and persistence forecasts paired with one future measurement."""

    rls_value: float
    persistence_value: float
    observed_value: float

    @property
    def rls_error(self) -> float:
        return self.observed_value - self.rls_value

    @property
    def persistence_error(self) -> float:
        return self.observed_value - self.persistence_value


def _timestamp_ms(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    timestamp = float(value)
    if timestamp < 10_000_000_000:
        timestamp *= 1000
    return round(timestamp)


def _processed_readings(export: dict[str, Any]) -> list[dict[str, Any]]:
    readings = export.get("readings", {})
    if not isinstance(readings, dict):
        return []
    records = readings.get("processed")
    if records is None:
        records = readings.get("raw", [])
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _soil_moisture_readings(
    export: dict[str, Any],
) -> tuple[
    dict[object, tuple[list[int], list[float]]],
    dict[tuple[object, object], tuple[int, float]],
]:
    readings_by_plant: dict[object, list[tuple[int, float]]] = {}
    readings_by_correlation: dict[tuple[object, object], tuple[int, float]] = {}

    for reading in _processed_readings(export):
        if reading.get("topic") != SOIL_MOISTURE_TOPIC:
            continue
        timestamp = _timestamp_ms(reading.get("time", reading.get("timestamp")))
        value = reading.get("value")
        if timestamp is None or isinstance(value, bool) or not isinstance(value, int | float):
            continue

        plant_id = reading.get("plant_id")
        correlation_id = reading.get("correlation_id")
        numeric_value = float(value)
        readings_by_plant.setdefault(plant_id, []).append((timestamp, numeric_value))
        if correlation_id is not None:
            readings_by_correlation[(plant_id, correlation_id)] = (timestamp, numeric_value)

    series_by_plant: dict[object, tuple[list[int], list[float]]] = {}
    for plant_id, readings in readings_by_plant.items():
        readings.sort(key=lambda reading: reading[0])
        series_by_plant[plant_id] = (
            [timestamp for timestamp, _ in readings],
            [value for _, value in readings],
        )
    return series_by_plant, readings_by_correlation


def match_forecasts(
    export: dict[str, Any],
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
    max_match_delay_seconds: int = DEFAULT_MAX_MATCH_DELAY_SECONDS,
) -> list[ForecastMatch]:
    """Match RLS and persistence forecasts with the same future measurements."""

    series_by_plant, readings_by_correlation = _soil_moisture_readings(export)
    forecasts = export.get("forecasts", [])
    if not isinstance(forecasts, list):
        return []

    matches: list[ForecastMatch] = []
    for forecast in forecasts:
        if not isinstance(forecast, dict) or forecast.get("metric") != "soil_moisture":
            continue
        if forecast.get("horizon_seconds") != horizon_seconds:
            continue

        forecast_time = _timestamp_ms(forecast.get("time", forecast.get("timestamp")))
        rls_value = forecast.get("predicted_value")
        plant_id = forecast.get("plant_id")
        correlation_id = forecast.get("correlation_id")
        current_reading = readings_by_correlation.get((plant_id, correlation_id))
        series = series_by_plant.get(plant_id)
        if (
            forecast_time is None
            or isinstance(rls_value, bool)
            or not isinstance(rls_value, int | float)
            or current_reading is None
            or series is None
        ):
            continue

        current_time, persistence_value = current_reading
        if current_time > forecast_time:
            continue

        reading_times, reading_values = series
        target_time = forecast_time + horizon_seconds * 1000
        reading_index = bisect_left(reading_times, target_time)
        if reading_index >= len(reading_times):
            continue

        match_delay_seconds = (reading_times[reading_index] - target_time) / 1000
        if match_delay_seconds > max_match_delay_seconds:
            continue

        matches.append(
            ForecastMatch(
                rls_value=float(rls_value),
                persistence_value=persistence_value,
                observed_value=reading_values[reading_index],
            )
        )

    return matches


def _error_metrics(errors: list[float]) -> dict[str, float | None]:
    if not errors:
        return {
            "mae": None,
            "rmse": None,
            "bias_observed_minus_predicted": None,
        }
    return {
        "mae": mean(abs(error) for error in errors),
        "rmse": sqrt(mean(error**2 for error in errors)),
        "bias_observed_minus_predicted": mean(errors),
    }


def evaluate_forecasts(
    export: dict[str, Any],
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
    max_match_delay_seconds: int = DEFAULT_MAX_MATCH_DELAY_SECONDS,
) -> dict[str, Any]:
    """Compare RLS and persistence errors on matched soil-moisture forecasts."""

    matches = match_forecasts(
        export,
        horizon_seconds=horizon_seconds,
        max_match_delay_seconds=max_match_delay_seconds,
    )
    return {
        "horizon_seconds": horizon_seconds,
        "max_match_delay_seconds": max_match_delay_seconds,
        "matched_forecasts": len(matches),
        "rls": _error_metrics([match.rls_error for match in matches]),
        "persistence": _error_metrics([match.persistence_error for match in matches]),
    }


def _empirical_cdf(values: list[float]) -> tuple[list[float], list[float]]:
    sorted_values = sorted(values)
    count = len(sorted_values)
    return sorted_values, [index / count for index in range(1, count + 1)]


def plot_forecasts(matches: list[ForecastMatch], output: Path) -> None:
    """Plot forecast calibration and cumulative absolute errors."""

    if not matches:
        raise ValueError("No matched forecasts are available to plot")

    import matplotlib.pyplot as plt

    rls_values = [match.rls_value for match in matches]
    persistence_values = [match.persistence_value for match in matches]
    observed_values = [match.observed_value for match in matches]
    rls_errors, rls_proportions = _empirical_cdf(
        [abs(match.rls_error) for match in matches]
    )
    persistence_errors, persistence_proportions = _empirical_cdf(
        [abs(match.persistence_error) for match in matches]
    )
    lower = min(*rls_values, *persistence_values, *observed_values)
    upper = max(*rls_values, *persistence_values, *observed_values)
    padding = max((upper - lower) * 0.05, 1.0)
    limits = (lower - padding, upper + padding)

    figure, (scatter_axis, error_axis) = plt.subplots(
        1,
        2,
        figsize=(10.4, 4.8),
        constrained_layout=True,
    )
    scatter_axis.scatter(
        rls_values,
        observed_values,
        s=14,
        alpha=0.45,
        edgecolors="none",
        label="RLS",
    )
    scatter_axis.scatter(
        persistence_values,
        observed_values,
        s=14,
        alpha=0.35,
        edgecolors="none",
        label="Persistence",
    )
    scatter_axis.plot(limits, limits, color="0.3", linewidth=1, linestyle="--")
    scatter_axis.set(
        title="Observed vs 3 h forecast soil moisture",
        xlabel="Forecast value (%)",
        ylabel="Observed value (%)",
        xlim=limits,
        ylim=limits,
    )
    scatter_axis.set_aspect("equal", adjustable="box")
    scatter_axis.legend()

    error_axis.step(
        [0.0, *rls_errors],
        [0.0, *rls_proportions],
        where="post",
        label="RLS",
    )
    error_axis.step(
        [0.0, *persistence_errors],
        [0.0, *persistence_proportions],
        where="post",
        label="Persistence",
    )
    error_axis.set(
        title="Cumulative absolute forecast error",
        xlabel="Absolute error (percentage points)",
        ylabel="Proportion of forecasts",
        xlim=(0, None),
        ylim=(0, 1.01),
    )
    error_axis.grid(alpha=0.2)
    error_axis.legend()

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def load_export(path: Path) -> dict[str, Any]:
    """Load an uncompressed or gzip-compressed Digital Twin JSON export."""

    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            export = json.load(handle)
    else:
        with path.open("r", encoding="utf-8") as handle:
            export = json.load(handle)
    if not isinstance(export, dict):
        raise ValueError("The export must contain a JSON object at its top level")
    return export


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="Path to the exported .json or .json.gz file")
    parser.add_argument("--plot", type=Path, help="Write the observed-versus-forecast plot")
    args = parser.parse_args()

    export = load_export(args.export)
    matches = match_forecasts(export)
    print(json.dumps(evaluate_forecasts(export), indent=2))
    if args.plot is not None:
        plot_forecasts(matches, args.plot)


if __name__ == "__main__":
    main()
