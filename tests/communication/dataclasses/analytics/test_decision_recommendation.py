import pytest

from dt.communication.dataclasses.analytics.recommendation import (
    ActionResult,
    Recommendation,
    RecommendedAction,
)


def test_recommendation_coerces_values() -> None:
    payload = Recommendation(
        plant_id="5",
        timestamp="1735000001",
        correlation_id=456,
        confidence="0.7",
        reason=777,
        actions=[
            {"capability": "irrigation", "command": 123, "duration_seconds": "5.5"},
            RecommendedAction(capability="advisory", command="inspect_plant"),
        ],
        action_results=[{"action_index": "0", "status": "accepted"}],
    )

    assert payload.plant_id == 5
    assert payload.timestamp == 1_735_000_001.0
    assert payload.correlation_id == "456"
    assert payload.confidence == 0.7
    assert payload.reason == "777"
    assert payload.actions == [
        RecommendedAction(capability="irrigation", command="123", duration_seconds=5.5),
        RecommendedAction(capability="advisory", command="inspect_plant"),
    ]
    assert payload.action_results == [ActionResult(action_index=0, status="accepted")]


def test_recommendation_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="actions"):
        Recommendation(
            plant_id=5,
            timestamp=1_735_000_001,
            correlation_id="corr-3",
            confidence=0.9,
            reason="dry soil",
            actions=[],
        )

    with pytest.raises(ValueError, match="confidence"):
        Recommendation(
            plant_id=5,
            timestamp=1_735_000_001,
            correlation_id="corr-3",
            confidence=1.1,
            reason="dry soil",
            actions=[RecommendedAction(capability="irrigation", command="ON")],
        )

    with pytest.raises(ValueError, match="reason"):
        Recommendation(
            plant_id=5,
            timestamp=1_735_000_001,
            correlation_id="corr-3",
            confidence=0.4,
            reason=" ",
            actions=[RecommendedAction(capability="irrigation", command="ON")],
        )
