from dt.communication.dataclasses.queries import (
    ActiveAlertsQuery,
    ActionHistoryQuery,
    AlertHistoryQuery,
    ForecastHistoryQuery,
    HealthHistoryQuery,
    ReadingsQuery,
    RecommendationHistoryQuery,
)


def test_readings_query_validates_window() -> None:
    """Reject unsupported aggregation window values.

    Returns
    -------
    None
        Assertions fail if invalid windows stop raising.
    """
    query = ReadingsQuery(window="raw")
    assert query.window == "raw"

    query = ReadingsQuery(window="1h")
    assert query.window == "1h"

    try:
        ReadingsQuery(window="5m")
    except ValueError as exc:
        assert str(exc) == "window must be 'raw' or '1h'"
    else:
        raise AssertionError("Expected ValueError for unsupported window")


def test_active_alerts_query_coerces_optional_plant_id() -> None:
    """Coerce optional plant_id into an int when provided.

    Returns
    -------
    None
        Assertions fail if plant_id casting changes.
    """
    query = ActiveAlertsQuery(plant_id="7")  # pyright: ignore[]
    assert query.plant_id == 7

    query = ActiveAlertsQuery()
    assert query.plant_id is None


def test_alert_history_query_validates_limit() -> None:
    """Reject non-positive limits and coerce plant_id to int.

    Returns
    -------
    None
        Assertions fail if validation rules change.
    """
    query = AlertHistoryQuery(plant_id="3", limit="5")  # pyright: ignore[]
    assert query.plant_id == 3
    assert query.limit == 5
    assert query.effective_limit == 5

    query = AlertHistoryQuery(plant_id="3", limit="5", since="1.0", until="2.0")  # pyright: ignore[]
    assert query.since == 1.0
    assert query.until == 2.0
    assert query.effective_limit is None

    query = AlertHistoryQuery(plant_id="3", limit="5", since="1.0")  # pyright: ignore[]
    assert query.since == 1.0
    assert query.effective_limit is None

    try:
        AlertHistoryQuery(limit=0)
    except ValueError as exc:
        assert str(exc) == "limit must be positive"
    else:
        raise AssertionError("Expected ValueError for non-positive limit")


def test_action_history_query_validates_required_plant_and_limit() -> None:
    query = ActionHistoryQuery(plant_id="3", limit="5")  # pyright: ignore[]
    assert query.plant_id == 3
    assert query.limit == 5
    assert query.effective_limit == 5

    query = ActionHistoryQuery(plant_id="3", limit="5", since="1.0")  # pyright: ignore[]
    assert query.since == 1.0
    assert query.effective_limit is None

    try:
        ActionHistoryQuery()
    except ValueError as exc:
        assert str(exc) == "plant_id is required"
    else:
        raise AssertionError("Expected ValueError for missing plant_id")

    try:
        ActionHistoryQuery(plant_id=1, limit=0)
    except ValueError as exc:
        assert str(exc) == "limit must be positive"
    else:
        raise AssertionError("Expected ValueError for non-positive limit")


def test_history_queries_reject_since_after_until() -> None:
    """Reject history ranges where since is after until.

    Returns
    -------
    None
        Assertions fail if range validation changes.
    """
    for query_type in (
        ActionHistoryQuery,
        AlertHistoryQuery,
        HealthHistoryQuery,
        ForecastHistoryQuery,
        RecommendationHistoryQuery,
    ):
        try:
            query_type(plant_id=1, since=20.0, until=10.0)
        except ValueError as exc:
            assert str(exc) == "since must be less than or equal to until"
        else:
            raise AssertionError("Expected ValueError for inverted history range")


def test_forecast_history_query_rejects_non_positive_horizon() -> None:
    """Reject non-positive forecast horizon values.

    Returns
    -------
    None
        Assertions fail if horizon validation changes.
    """
    try:
        ForecastHistoryQuery(plant_id=1, horizon_seconds=0)
    except ValueError as exc:
        assert str(exc) == "horizon_seconds must be positive"
    else:
        raise AssertionError("Expected ValueError for non-positive horizon")
