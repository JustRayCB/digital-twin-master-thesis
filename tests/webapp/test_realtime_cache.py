from dt.webapp.consumer import update_latest_payload_cache


def test_update_latest_payload_cache_stores_latest_per_topic():
    cache: dict[str, dict] = {}

    update_latest_payload_cache(cache, "topic-a", {"time": 1})
    update_latest_payload_cache(cache, "topic-b", {"time": 2})

    assert cache == {"topic-a": {"time": 1}, "topic-b": {"time": 2}}


def test_update_latest_payload_cache_overwrites_existing_topic():
    cache: dict[str, dict] = {"topic-a": {"time": 1}}

    update_latest_payload_cache(cache, "topic-a", {"time": 2})

    assert cache == {"topic-a": {"time": 2}}
