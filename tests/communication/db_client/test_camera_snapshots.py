"""Integration tests for camera snapshot database API client methods."""

from __future__ import annotations

import pytest

from dt.communication.dataclasses import CameraSnapshot, SensorDescriptor
from dt.communication.dataclasses.queries import CameraSnapshotQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics

pytestmark = [pytest.mark.requires_timescale]


def test_get_latest_camera_snapshot_reads_real_api_payload(
    database_api_client: DatabaseApiClient,
    snapshot_store,
    sensor: SensorDescriptor,
) -> None:
    """Fetch the latest camera snapshot from the real database API."""
    snapshot = CameraSnapshot(
        plant_id=sensor.plant_id,
        sensor_id=sensor.id,
        timestamp=1_735_689_600.0,
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="cam-corr-1",
        mime_type="image/jpeg",
        image="AQI=",
        width=640,
        height=480,
    )
    snapshot_store.ingest_camera_snapshot(snapshot)

    result = database_api_client.get_latest_camera_snapshot(plant_id=sensor.plant_id)

    assert result == snapshot


def test_get_latest_camera_snapshot_returns_none_on_real_404(
    database_api_client: DatabaseApiClient,
) -> None:
    """Return None when the real database API has no snapshot for the plant."""
    assert database_api_client.get_latest_camera_snapshot(plant_id=999) is None


def test_get_latest_camera_snapshot_wraps_real_request_failures() -> None:
    """Raise RuntimeError when the camera snapshot API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="Failed to fetch latest camera snapshot"):
        client.get_latest_camera_snapshot(plant_id=1)


def test_query_camera_snapshots_reads_real_api_payloads(
    database_api_client: DatabaseApiClient,
    snapshot_store,
    sensor: SensorDescriptor,
) -> None:
    """Fetch interval-filtered camera snapshots from the real database API."""
    for timestamp, correlation_id in (
        (1_735_689_600.0, "cam-corr-1"),
        (1_735_689_700.0, "cam-corr-2"),
        (1_735_689_800.0, "cam-corr-3"),
    ):
        snapshot_store.ingest_camera_snapshot(
            CameraSnapshot(
                plant_id=sensor.plant_id,
                sensor_id=sensor.id,
                timestamp=timestamp,
                topic=Topics.CAMERA_IMAGE_TOP,
                correlation_id=correlation_id,
                mime_type="image/jpeg",
                image="AQI=",
                width=640,
                height=480,
            )
        )

    result = database_api_client.query_camera_snapshots(
        CameraSnapshotQuery(
            plant_id=sensor.plant_id,
            since=1_735_689_650.0,
            until=1_735_689_750.0,
        )
    )

    assert [snapshot.correlation_id for snapshot in result] == ["cam-corr-2"]
