from dt.communication.adapters import dump, load
from dt.communication.dataclasses import CameraSnapshot
from dt.communication.topics import Topics


def test_camera_snapshot_roundtrip_generic_adapter() -> None:
    snapshot = CameraSnapshot(
        plant_id=1,
        sensor_id=99,
        timestamp=1_736_000_000,
        topic=Topics.CAMERA_IMAGE,
        correlation_id="cam-corr-1",
        mime_type="image/jpeg",
        image="/9j/4AAQSkZJRgABAQAAAQABAAD",
        width=640,
        height=480,
    )

    encoded = dump("generic", snapshot)
    restored = load("generic", CameraSnapshot, encoded)

    assert restored == snapshot
    assert restored.topic is Topics.CAMERA_IMAGE


def test_camera_snapshot_coerces_field_types() -> None:
    payload = CameraSnapshot(
        plant_id="1",
        sensor_id="99",
        timestamp="1736000000.5",
        topic="dt.sensors.camera_image",
        correlation_id=123,
        mime_type=1234,
        image=12345,
        width="640",
        height="480",
    )

    assert payload.plant_id == 1
    assert payload.sensor_id == 99
    assert payload.timestamp == 1_736_000_000.5
    assert payload.topic is Topics.CAMERA_IMAGE
    assert payload.correlation_id == "123"
    assert payload.mime_type == "1234"
    assert payload.image == "12345"
    assert payload.width == 640
    assert payload.height == 480
