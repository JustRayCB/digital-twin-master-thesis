from .base import NormalizationStrategy


class IdentityNormalization(NormalizationStrategy):
    """Return normalized values unchanged."""

    def apply(self, value: float) -> float:
        return float(value)
