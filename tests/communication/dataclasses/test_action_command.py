from dt.communication.adapters import dump, load
from dt.communication.dataclasses.action_command import ActionCommand


def test_action_command_serialization_roundtrip() -> None:
    """Round-trip ActionCommand through the generic adapter.

    Returns
    -------
    None
        Assertions fail if coercion or serialization deviates.
    """
    payload = ActionCommand(
        plant_id="1",
        action_id=123,
        actuator_id="7",
        timestamp=10,
        duration="2.5",
        command="ON",
        reason="manual_override",
        correlation_id="corr-123",
    )

    assert payload.plant_id == 1
    assert payload.action_id == "123"
    assert payload.actuator_id == 7
    assert payload.timestamp == 10.0
    assert payload.duration == 2.5
    assert payload.command == "ON"
    assert payload.reason == "manual_override"
    assert payload.correlation_id == "corr-123"

    encoded = dump("generic", payload)
    decoded = load("generic", ActionCommand, encoded)
    assert decoded == payload
