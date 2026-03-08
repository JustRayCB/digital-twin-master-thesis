from collections.abc import Mapping

from dt.communication.dataclasses.processed_sensor_data import ValidationFlag

# Ordered tuple ensures deterministic weighting.
FLAG_ORDER: tuple[ValidationFlag, ...] = (
    ValidationFlag.RANGE,
    ValidationFlag.RATE_OF_CHANGE,
    ValidationFlag.STUCK,
)

FLAG_WEIGHTS = {
    ValidationFlag.RANGE: "range_ok",
    ValidationFlag.RATE_OF_CHANGE: "roc_ok",
    ValidationFlag.STUCK: "stuck_ok",
}


def compute_dq_score(flags: Mapping[ValidationFlag, bool], weights: Mapping[str, float]) -> float:
    """Compute a weighted data-quality score from validation flags.

    Parameters
    ----------
    flags : Mapping[ValidationFlag, bool]
        Mapping describing the boolean outcome of each validation rule.
    weights : Mapping[str, float]
        Configuration weights keyed by the *_ok identifiers (for example
        "range_ok") used to scale contributions to the score.

    Returns
    -------
    float
        Weighted score on the interval [0, 1].

    Notes
    -----
    When no configured weights are present the score collapses to 0 unless all
    checks pass, in which case the function returns the neutral score of 1.
    """
    total_weight = 0.0
    passing_weight = 0.0

    for flag in FLAG_ORDER:
        weight_key = FLAG_WEIGHTS[flag]
        weight = float(weights.get(weight_key, 0.0))
        total_weight += weight
        if not bool(flags.get(flag, False)):
            passing_weight += weight

    if total_weight <= 0.0:
        return 1.0 if all(not bool(flags.get(flag, False)) for flag in FLAG_ORDER) else 0.0

    score = passing_weight / total_weight
    return max(0.0, min(1.0, score))
