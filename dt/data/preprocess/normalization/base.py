from abc import ABC, abstractmethod


class NormalizationStrategy(ABC):
    """Scale calibrated values into normalized ranges."""

    @abstractmethod
    def apply(self, value: float) -> float:
        """Return the normalized value for ``value``."""
