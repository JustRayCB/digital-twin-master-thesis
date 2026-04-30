import pytest

from dt.communication.dataclasses.analytics.health_assessment import (
    HealthAssessment,
    HealthState,
)


def test_health_assessment_coerces_values() -> None:
    payload = HealthAssessment(
        plant_id="7",
        timestamp="1735000000.25",
        correlation_id=123,
        state="healthy",
        score="0.85",
        confidence="0.65",
        summary=987,
    )

    assert payload.plant_id == 7
    assert payload.timestamp == 1_735_000_000.25
    assert payload.correlation_id == "123"
    assert payload.state is HealthState.HEALTHY
    assert payload.score == 0.85
    assert payload.confidence == 0.65
    assert payload.summary == "987"


def test_health_assessment_accepts_unknown_state_with_missing_score() -> None:
    payload = HealthAssessment(
        plant_id=1,
        timestamp=1_735_000_000,
        correlation_id="corr-1",
        state="unknown",
        score=None,
        confidence=0.2,
        summary="insufficient evidence",
    )

    assert payload.state is HealthState.UNKNOWN
    assert payload.score is None
    assert payload.confidence == 0.2


@pytest.mark.parametrize(
    "state",
    [HealthState.HEALTHY, HealthState.STRESSED, HealthState.CRITICAL],
)
def test_health_assessment_rejects_missing_score_for_known_states(
    state: HealthState,
) -> None:
    with pytest.raises(ValueError, match="score"):
        HealthAssessment(
            plant_id=1,
            timestamp=1_735_000_000,
            correlation_id="corr-1",
            state=state,
            score=None,
            summary="known state requires score",
        )


def test_health_assessment_requires_operational_fields() -> None:
    with pytest.raises(ValueError, match="timestamp"):
        HealthAssessment(
            plant_id=1,
            timestamp=0,
            correlation_id="corr-1",
            state=HealthState.STRESSED,
            score=0.4,
            summary="stressed",
        )

    with pytest.raises(ValueError, match="correlation_id"):
        HealthAssessment(
            plant_id=1,
            timestamp=1_735_000_000,
            correlation_id=" ",
            state=HealthState.STRESSED,
            score=0.4,
            summary="stressed",
        )


def test_health_assessment_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        HealthAssessment(
            plant_id=1,
            timestamp=1_735_000_000,
            correlation_id="corr-1",
            state=HealthState.STRESSED,
            score=0.4,
            confidence=1.1,
            summary="stressed",
        )


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_health_assessment_rejects_out_of_range_score(score: float) -> None:
    with pytest.raises(ValueError, match="score"):
        HealthAssessment(
            plant_id=1,
            timestamp=1_735_000_000,
            correlation_id="corr-1",
            state=HealthState.STRESSED,
            score=score,
            summary="stressed",
        )
