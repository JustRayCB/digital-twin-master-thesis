"""Reproduce the observation series and pump counts reported in the AI4DT paper.

The export's readings.raw array contains processed, quality-scored observations.
Soil moisture uses daily medians of those observations. Image features use daily
medians of hourly means, keeping only hours with mean light above 100 lux.
Calendar dates and Figure 2 day offsets use Europe/Brussels.
"""

import argparse
import gzip
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("Europe/Brussels")
IMAGE_METRICS = ("green_ratio", "leaf_count", "plant_height")
METRICS = ("soil_moisture", *IMAGE_METRICS)


def local_time(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC).astimezone(LOCAL_TIMEZONE)


def daily_series(export: dict) -> list[dict]:
    """Build the daily values plotted in Figure 2, leaving missing days empty."""
    soil_by_date = defaultdict(list)
    hourly_values = defaultdict(list)
    for record in export["readings"]["raw"]:
        metric = record["topic"].removeprefix("dt.sensors.")
        if metric == "soil_moisture":
            soil_by_date[local_time(record["time"]).date()].append(record["value"])
        elif metric in (*IMAGE_METRICS, "light_intensity"):
            hour = record["time"] // 3_600_000
            hourly_values[(metric, hour)].append(record["value"])

    hourly_means = {key: mean(values) for key, values in hourly_values.items()}
    images_by_date = defaultdict(list)
    for (metric, hour), value in hourly_means.items():
        if metric in IMAGE_METRICS and hourly_means.get(("light_intensity", hour), 0) > 100:
            date = local_time(hour * 3_600_000).date()
            images_by_date[(metric, date)].append(value)

    first_date = local_time(export["metadata"]["since"]).date()
    last_date = local_time(export["metadata"]["until"]).date()
    rows = []
    for day in range((last_date - first_date).days + 1):
        date = first_date + timedelta(days=day)
        row = {"date": date.isoformat(), "day": day}
        for metric in METRICS:
            values = (
                soil_by_date[date] if metric == "soil_moisture" else images_by_date[(metric, date)]
            )
            row[metric] = round(median(values), 2) if values else None
        rows.append(row)
    return rows


def pump_events(export: dict) -> list[dict]:
    """Collapse pump ON records by execution ID; OFF commands are not requests."""
    pump_id = next(
        actuator["id"] for actuator in export["plant"]["actuators"] if actuator["name"] == "pump"
    )
    executions = defaultdict(list)
    for record in export["actions"]:
        if record["actuator_id"] == pump_id and record["command"] == "ON":
            executions[record["execution_id"]].append(record)

    first_date = local_time(export["metadata"]["since"]).date()
    events = []
    for execution_id, records in executions.items():
        ordered = sorted(records, key=lambda record: record["time"])
        first = ordered[0]
        terminal = next(
            (record for record in reversed(ordered) if record["status"] != "running"),
            ordered[-1],
        )
        start = local_time(first["time"])
        seconds = start.hour * 3600 + start.minute * 60 + start.second + start.microsecond / 1e6
        events.append(
            {
                "execution_id": execution_id,
                "time_local": start.isoformat(),
                "day": round((start.date() - first_date).days + seconds / 86400, 6),
                "source": first["source"],
                "status": terminal["status"],
                "requested_duration_seconds": first["duration"],
                "reason": terminal.get("error_message") or terminal.get("reason"),
            }
        )
    return sorted(events, key=lambda event: event["time_local"])


def run_summary(export: dict, events: list[dict]) -> dict:
    """Count observations, estimator outputs, and pump requests."""
    readings = export["readings"]["raw"]
    topics = Counter(record["topic"] for record in readings)
    states = Counter(record["state"] for record in export["health"])
    counts = Counter((event["source"], event["status"]) for event in events)
    rejected = Counter(
        event["reason"]
        for event in events
        if event["source"] == "ai" and event["status"] == "rejected"
    )
    ranges = {}
    for metric in METRICS:
        values = [
            record["value"] for record in readings if record["topic"] == f"dt.sensors.{metric}"
        ]
        ranges[metric] = {"min": min(values), "max": max(values)} if values else None
    return {
        "timezone": str(LOCAL_TIMEZONE),
        "since_local": local_time(export["metadata"]["since"]).isoformat(),
        "until_local": local_time(export["metadata"]["until"]).isoformat(),
        "observations_total": len(readings),
        "observations_per_topic": dict(sorted(topics.items())),
        "observation_ranges": ranges,
        "health_assessments_total": sum(states.values()),
        "health_states": {
            state: {"count": count, "share_percent": round(100 * count / sum(states.values()), 1)}
            for state, count in sorted(states.items())
        },
        "pump": {
            "manual_completed": counts[("manual", "completed")],
            "autonomous_requests": sum(
                count for (source, _), count in counts.items() if source == "ai"
            ),
            "autonomous_completed": counts[("ai", "completed")],
            "autonomous_rejected": counts[("ai", "rejected")],
            "rejection_reasons": dict(sorted(rejected.items())),
        },
    }


def plot_run(rows: list[dict], events: list[dict], summary: dict, output: Path) -> None:
    """Plot daily observations, estimator-output shares, and pump requests."""
    import matplotlib.pyplot as plt
    import numpy as np

    figure, axes = plt.subplot_mosaic(
        [["green_ratio", "leaf_count"], ["plant_height", "health"], ["soil", "soil"]],
        figsize=(11, 9),
        constrained_layout=True,
    )
    days = [row["day"] for row in rows]
    for metric, title, unit, color in (
        ("green_ratio", "Green-pixel ratio", "%", "#0072B2"),
        ("leaf_count", "Leaf count", "Estimated count", "#E69F00"),
        ("plant_height", "Plant height", "cm", "#009E73"),
        ("soil_moisture", "Soil moisture and pump requests", "%", "#0072B2"),
    ):
        axis = axes["soil" if metric == "soil_moisture" else metric]
        values = [row[metric] if row[metric] is not None else float("nan") for row in rows]
        axis.plot(days, values, color=color)
        axis.set(title=title, ylabel=unit)
        axis.grid(alpha=0.2)
        ticks = sorted({0, len(rows) // 2, len(rows) - 1})
        axis.set_xticks(
            [days[index] for index in ticks],
            [datetime.fromisoformat(rows[index]["date"]).strftime("%d %b") for index in ticks],
        )
        axis.set_xlabel("Date (Europe/Brussels)")

    states = ("healthy", "stressed", "critical")
    shares = [summary["health_states"].get(state, {}).get("share_percent", 0) for state in states]
    bars = axes["health"].bar(states, shares, color=["#009E73", "#E69F00", "#D55E00"])
    axes["health"].bar_label(bars, labels=[f"{share:.1f}%" for share in shares], padding=3)
    axes["health"].set(
        title="Estimator outputs (not biologically validated)",
        ylabel="Share of recorded assessments (%)",
        ylim=(0, 100),
    )

    soil = [
        row["soil_moisture"] if row["soil_moisture"] is not None else float("nan") for row in rows
    ]
    for source, status, label, marker, color in (
        ("manual", "completed", "Manual", "o", "#666666"),
        ("ai", "completed", "Executed autonomous", "^", "#009E73"),
        ("ai", "rejected", "Rejected autonomous", "x", "#D55E00"),
    ):
        selected = [
            event for event in events if event["source"] == source and event["status"] == status
        ]
        event_days = [event["day"] for event in selected]
        axes["soil"].scatter(
            event_days,
            np.interp(event_days, days, soil, left=np.nan, right=np.nan),
            marker=marker,
            color=color,
            s=45,
            zorder=3,
            label=f"{label} (n={len(selected)})",
        )
    axes["soil"].legend(loc="lower left", bbox_to_anchor=(0, 1), ncol=3, fontsize=9)
    axes["soil"].set_title("Soil moisture and pump requests", pad=30)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="Path to the case-study .json or .json.gz export")
    parser.add_argument("--plot", type=Path, help="Write the observation and pump-request figure")
    args = parser.parse_args()
    opener = gzip.open if args.export.suffix == ".gz" else open
    with opener(args.export, "rt", encoding="utf-8") as handle:
        export = json.load(handle)

    events = pump_events(export)
    summary = run_summary(export, events)
    print(json.dumps(summary, indent=2))
    if args.plot is not None:
        plot_run(daily_series(export), events, summary, args.plot)


if __name__ == "__main__":
    main()
