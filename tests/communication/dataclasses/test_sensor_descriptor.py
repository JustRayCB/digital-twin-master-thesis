from dt.communication.dataclasses import SensorDescriptor


def test_sensor_descriptor_metadata_and_mutation():
    """Check SensorDescriptor coerces inputs and supports runtime ID updates.

    Returns
    -------
    None
        Assertions fail if descriptor coercion or ID mutation regresses.
    """

    metadata = SensorDescriptor(sensor_id=1, name="123", pin=11, read_interval=15)

    assert metadata.sensor_id == 1
    assert metadata.name == "123"
    assert metadata.pin == 11
    assert metadata.read_interval == 15

    metadata.change_id(9)
    assert metadata.sensor_id == 9
