import pytest

from dt.communication.dataclasses.analytics.recommendation import (
    ActionResult,
)


def test_action_result_coerces_values() -> None:
    payload = ActionResult(action_index="4", status="accepted")

    assert payload.action_index == 4
    assert payload.status == "accepted"


@pytest.mark.parametrize("status", ["accepted", "advisory_only", "rejected", "failed"])
def test_action_result_accepts_allowed_statuses(status: str) -> None:
    payload = ActionResult(action_index=0, status=status)

    assert payload.status == status


def test_action_result_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="status"):
        ActionResult(
            action_index=0,
            status="queued",
        )

    with pytest.raises(ValueError, match="action_index"):
        ActionResult(action_index=-1, status="accepted")
