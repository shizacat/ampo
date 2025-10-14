import pytest
import datetime as dt
from typing import Optional

from ampo import CollectionWorker, ORMConfig


def test_getter_setter_lock_field():
    """
    Test getter and setter for lock_field property
    """
    class TestWorker(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test",
            orm_lock_record={
                "lock_field": "is_locked",
                "lock_field_time_start": "lock_start_time",
            }
        )

        field1: str
        is_locked: bool = False
        lock_start_time: Optional[dt.datetime] = None

    # Create instance
    worker = TestWorker(field1="test")

    # Test initial state
    assert worker.lock_field is False

    # Test setter with valid boolean value
    worker.lock_field = True
    assert worker.lock_field is True
    assert worker.is_locked is True

    # Test setter with False
    worker.lock_field = False
    assert worker.lock_field is False
    assert worker.is_locked is False

    # Test setter with invalid type
    with pytest.raises(TypeError, match="Got not bool"):
        worker.lock_field = "invalid"

    # Test setter with integer
    with pytest.raises(TypeError, match="Got not bool"):
        worker.lock_field = 1


def test_getter_setter_lock_field_time_start():
    """
    Test getter and setter for lock_field_time_start property
    """
    class TestWorker(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test",
            orm_lock_record={
                "lock_field": "is_locked",
                "lock_field_time_start": "lock_start_time",
            }
        )

        field1: str
        is_locked: bool = False
        lock_start_time: Optional[dt.datetime] = None

    # Create instance
    worker = TestWorker(field1="test")

    # Test initial state
    assert worker.lock_field_time_start is None

    # Test setter with valid datetime
    test_time = dt.datetime.now(dt.timezone.utc)
    worker.lock_field_time_start = test_time
    assert worker.lock_field_time_start == test_time
    assert worker.lock_start_time == test_time

    # Test setter with invalid type
    with pytest.raises(TypeError, match="Got not datetime"):
        worker.lock_field_time_start = "invalid"

    # Test setter with integer
    with pytest.raises(TypeError, match="Got not datetime"):
        worker.lock_field_time_start = 1234567890


def test__get_cfg_lock_record_check_cache_01():
    """
    Test _get_cfg_lock_record method

    Test case 1: When lock record is configured (should work normally)
    """
    class TestWorkerWithLock(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test_with_lock",
            orm_lock_record={
                "lock_field": "is_locked",
                "lock_field_time_start": "lock_start_time",
                "lock_max_period_sec": 900,
            }
        )

        field1: str
        is_locked: bool = False
        lock_start_time: Optional[dt.datetime] = None

    # Test that _get_cfg_lock_record works when configured
    cfg_lock_record = TestWorkerWithLock._get_cfg_lock_record()
    assert cfg_lock_record.lock_field == "is_locked"
    assert cfg_lock_record.lock_field_time_start == "lock_start_time"
    assert cfg_lock_record.lock_max_period_sec == 900
    assert cfg_lock_record.allow_find_locked is True

    # Test cache functionality - second call should return the same object
    cfg_lock_record2 = TestWorkerWithLock._get_cfg_lock_record()
    assert cfg_lock_record is cfg_lock_record2  # Same object due to cache


def test__get_cfg_lock_record_check_cache_02():
    """
    Test _get_cfg_lock_record method

    # Test case 2: When lock record is disabled (should raise ValueError)
    """
    class TestWorkerWithoutLock(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test_without_lock"
        )

        field1: str

    # Test that _get_cfg_lock_record raises ValueError when not configured
    with pytest.raises(ValueError, match="Lock record is not enabled"):
        TestWorkerWithoutLock._get_cfg_lock_record()

    # Test that the exception is raised consistently
    # (cache should not affect this)
    with pytest.raises(ValueError, match="Lock record is not enabled"):
        TestWorkerWithoutLock._get_cfg_lock_record()


def test__get_cfg_lock_record_check_cache_03():
    """
    Test _get_cfg_lock_record method

    # Test case 3: Additional test with different lock configuration
    """
    class TestWorkerWithCustomLock(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test_custom_lock",
            orm_lock_record={
                "lock_field": "locked",
                "lock_field_time_start": "lock_time",
                "lock_max_period_sec": 0,  # No expiration
            }
        )

        field1: str
        locked: bool = False
        lock_time: Optional[dt.datetime] = None

    # Test custom configuration
    cfg_custom = TestWorkerWithCustomLock._get_cfg_lock_record()
    assert cfg_custom.lock_field == "locked"
    assert cfg_custom.lock_field_time_start == "lock_time"
    assert cfg_custom.lock_max_period_sec == 0
    assert cfg_custom.allow_find_locked is False

    # Verify cache works for custom configuration too
    cfg_custom2 = TestWorkerWithCustomLock._get_cfg_lock_record()
    assert cfg_custom is cfg_custom2
