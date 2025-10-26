from dt.communication.dataclasses import DBTimestampQuery


def test_db_timestamp_query_behaviour():
    """Ensure DBTimestampQuery coerces types and handles timestamp conversions.

    Returns
    -------
    None
        The assertions raise if JSON helpers or conversion logic change.
    """

    query = DBTimestampQuery(data_type="42", since=2000, until=5000)

    assert query.data_type == "42"
    assert query.since == 2000
    assert query.until == 5000

    query.js_to_py_timestamp()
    assert query.since == 2
    assert query.until == 5

    encoded = {
        "data_type": "soil_moisture",
        "since": 1000,
        "until": 2000,
    }
    round_trip = DBTimestampQuery.from_json(encoded)
    assert round_trip.data_type == "soil_moisture"
    assert round_trip.since == 1000
    assert round_trip.until == 2000
