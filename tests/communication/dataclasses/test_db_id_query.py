import pytest

from dt.communication.dataclasses import DBIdQuery


def test_db_id_query_rejects_invalid_bounds():
    """Confirm DBIdQuery enforces positive sensor IDs and limits.

    Returns
    -------
    None
        Pytest raises when validation fails to guard invalid inputs.
    """

    with pytest.raises(ValueError, match="Limit must be greater than 0"):
        DBIdQuery(sensor_id=1, limit=0)

    with pytest.raises(ValueError, match="Sensor id must be greater than 0"):
        DBIdQuery(sensor_id=0, limit=1)
