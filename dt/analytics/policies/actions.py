"""Recommendation action identifiers."""

from enum import StrEnum


class RecommendationAction(StrEnum):
    """Stable recommendation identifiers emitted by analytics policy."""

    IRRIGATE_NOW = "irrigate_now"
    INSPECT_PLANT = "inspect_plant"


def is_controller_dispatch_candidate(action: RecommendationAction | str) -> bool:
    """Return whether a recommendation maps to a controller execution path."""

    normalized_action = RecommendationAction(action)
    return normalized_action is RecommendationAction.IRRIGATE_NOW
