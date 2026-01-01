from enum import StrEnum


class AlertType(StrEnum):
    """Discriminator for polymorphic alert deserialization."""

    SENSOR = "sensor"
    EXTERNAL = "external"
