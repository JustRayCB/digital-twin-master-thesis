"""Evaluate three-hour soil-moisture forecasts against later measurements.

Usage:
    python scripts/evaluate_forecasts.py \
        docs/data/dtwin-data-2026-05-15T11-25-11-175Z.json.gz \
        --plot forecast-validation.png

For each forecast, the script selects the first soil-moisture measurement at or
after its target time. Matches delayed by more than 5 minutes are excluded.
Errors are defined as observed value minus predicted value.
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
    """A forecast paired with the first measurement after its target time."""

    predicted_value: float
    observed_value: float

    @property
    def error(self) -> float:
        """Return observed value minus predicted value."""

        return self.observed_value - self.predicted_value


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


def _soil_moisture_series(
    export: dict[str, Any],
) -> dict[object, tuple[list[int], list[float]]]:
    readings_by_plant: dict[object, list[tuple[int, float]]] = {}
    for reading in _processed_readings(export):
        if reading.get("topic") != SOIL_MOISTURE_TOPIC:
            continue
        timestamp = _timestamp_ms(reading.get("time", reading.get("timestamp")))
        value = reading.get("value")
        if timestamp is None or isinstance(value, bool) or not isinstance(value, int | float):
            continue
        readings_by_plant.setdefault(reading.get("plant_id"), []).append((timestamp, float(value)))

    series_by_plant: dict[object, tuple[list[int], list[float]]] = {}
    for plant_id, readings in readings_by_plant.items():
        readings.sort(key=lambda reading: reading[0])
        series_by_plant[plant_id] = (
            [timestamp for timestamp, _ in readings],
            [value for _, value in readings],
        )
    return series_by_plant


def match_forecasts(
    export: dict[str, Any],
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
    max_match_delay_seconds: int = DEFAULT_MAX_MATCH_DELAY_SECONDS,
) -> list[ForecastMatch]:
    """Match fixed-horizon forecasts with subsequent measurements."""

    series_by_plant = _soil_moisture_series(export)
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
        predicted_value = forecast.get("predicted_value")
        if (
            forecast_time is None
            or isinstance(predicted_value, bool)
            or not isinstance(predicted_value, int | float)
        ):
            continue

        series = series_by_plant.get(forecast.get("plant_id"))
        if series is None:
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
                predicted_value=float(predicted_value),
                observed_value=reading_values[reading_index],
            )
        )

    return matches


def evaluate_forecasts(
    export: dict[str, Any],
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
    max_match_delay_seconds: int = DEFAULT_MAX_MATCH_DELAY_SECONDS,
) -> dict[str, int | float | None]:
    """Compute error metrics for matched soil-moisture forecasts."""

    matches = match_forecasts(
        export,
        horizon_seconds=horizon_seconds,
        max_match_delay_seconds=max_match_delay_seconds,
    )
    result: dict[str, int | float | None] = {
        "horizon_seconds": horizon_seconds,
        "max_match_delay_seconds": max_match_delay_seconds,
        "matched_forecasts": len(matches),
        "mae": None,
        "rmse": None,
        "bias_observed_minus_predicted": None,
    }
    if not matches:
        return result

    errors = [match.error for match in matches]
    result.update(
        {
            "mae": mean(abs(error) for error in errors),
            "rmse": sqrt(mean(error**2 for error in errors)),
            "bias_observed_minus_predicted": mean(errors),
        }
    )
    return result


def plot_forecasts(matches: list[ForecastMatch], output: Path) -> None:
    """Plot observed soil moisture against three-hour forecasts."""

    if not matches:
        raise ValueError("No matched forecasts are available to plot")

    import matplotlib.pyplot as plt

    predicted = [match.predicted_value for match in matches]
    observed = [match.observed_value for match in matches]
    lower = min(*predicted, *observed)
    upper = max(*predicted, *observed)
    padding = max((upper - lower) * 0.05, 1.0)
    limits = (lower - padding, upper + padding)

    figure, axis = plt.subplots(figsize=(5.2, 5.0), constrained_layout=True)
    axis.scatter(predicted, observed, s=14, alpha=0.55, edgecolors="none")
    axis.plot(limits, limits, color="0.3", linewidth=1, linestyle="--")
    axis.set(
        title="Observed vs 3 h forecast soil moisture",
        xlabel="Forecast value (%)",
        ylabel="Observed value (%)",
        xlim=limits,
        ylim=limits,
    )
    axis.set_aspect("equal", adjustable="box")

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
    metrics = evaluate_forecasts(export)
    print(json.dumps(metrics, indent=2))
    if args.plot is not None:
        plot_forecasts(match_forecasts(export), args.plot)


if __name__ == "__main__":
    main()
