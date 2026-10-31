import json
import pytest
from datetime import date
from scripts.recovery import (
    pending_batches,
    collect_with_retry,
    retryable
)


def test_completed_batch_detection(tmp_path):
    log = tmp_path / "backfill.jsonl"
    log.write_text(json.dumps({
        "symbol": "GP",
        "start": "2026-04-30",
        "end": "2026-05-06",
        "status": "success",
        "fetched": 5
    }) + "\n", encoding="utf-8")

    missing = pending_batches(
        "GP",
        date(2026, 4, 30),
        date(2026, 5, 13),
        log
    )

    assert len(missing) == 1
    assert str(missing[0][0]) == "2026-05-07"


def test_retry_temporary_error():
    calls = []

    def fake_fetch(*args):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("Temporary timeout")
        return {"fetched": 5, "inserted": 5}

    result = collect_with_retry(
        "GP", "2026-10-20", "2026-10-26",
        fetcher=fake_fetch,
        sleeper=lambda seconds: None
    )

    assert len(calls) == 2
    assert result["fetched"] == 5


def test_no_retry_on_403():
    calls = []

    def blocked(*args):
        calls.append(1)
        raise ConnectionError("HTTP 403 Forbidden")

    with pytest.raises(ConnectionError):
        collect_with_retry(
            "GP", "2026-10-20", "2026-10-26",
            fetcher=blocked,
            sleeper=lambda seconds: None
        )

    assert len(calls) == 1


def test_retry_exhaustion():
    calls = []

    def timeout(*args):
        calls.append(1)
        raise TimeoutError("Temporary timeout")

    with pytest.raises(TimeoutError):
        collect_with_retry(
            "GP", "2026-10-20", "2026-10-26",
            fetcher=timeout,
            sleeper=lambda seconds: None
        )

    assert len(calls) == 2


def test_permission_errors_not_retryable():
    assert retryable(ConnectionError("403 Forbidden")) is False
    assert retryable(TimeoutError("Timeout")) is True
