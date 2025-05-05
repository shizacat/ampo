import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from ampo import AMPODatabase, CollectionWorker, ORMConfig, init_collection


# Configure
mongo_url = os.environ.get("TEST_MONGO_URL", None)


# --- Fixture ---
@pytest_asyncio.fixture
async def ampo_db():
    try:
        db = AMPODatabase(url=mongo_url)
        # Clear collection
        await db._client.drop_database(db._client.get_default_database())
        await init_collection()
        yield db
    finally:
        AMPODatabase.clear()


# --- Tests ----

@pytest.mark.asyncio
@pytest.mark.skipif(not mongo_url, reason="Set mongo_url")
async def test_hook_pre_save(ampo_db: AMPODatabase):
    # hooks
    h = AsyncMock()

    # Create model with hooos
    class Model(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test",
            orm_hooks={
                "pre_save": [h,],
                "post_save": [AsyncMock(),],
            }
        )
        f1: str

    a = Model(f1="test")

    # Call #1
    await a.save()
    # Check, hook was called
    h.assert_awaited_once()

    # Call #2, with context
    await a.save({"a": 1})
    # Check, hook was called
    h.assert_awaited()
    # Check context
    args, kwargs = h.call_args_list[1]
    assert isinstance(args[0], Model)
    assert args[1], {"a": 1}


@pytest.mark.asyncio
@pytest.mark.skipif(not mongo_url, reason="Set mongo_url")
async def test_hook_post_save(ampo_db: AMPODatabase):
    h = AsyncMock()

    class Model(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test_post_save",
            orm_hooks={
                "pre_save": [AsyncMock()],
                "post_save": [h],
            }
        )
        f1: str

    a = Model(f1="post")

    # Call #1
    await a.save()
    h.assert_awaited_once()

    # Call #2 with context
    await a.save({"ctx": "post"})
    assert h.await_count == 2
    args, kwargs = h.call_args_list[1]
    assert isinstance(args[0], Model)
    assert args[1] == {"ctx": "post"}


@pytest.mark.asyncio
@pytest.mark.skipif(not mongo_url, reason="Set mongo_url")
async def test_hook_pre_delete(ampo_db: AMPODatabase):
    h = AsyncMock()

    class Model(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test_pre_delete",
            orm_hooks={
                "pre_delete": [h],
            }
        )
        f1: str

    a = Model(f1="pre")
    await a.save()

    # Call #1
    await a.delete()
    h.assert_awaited_once()

    # Call #2 with context
    await a.delete({"ctx": "pre"})
    assert h.await_count == 2
    args, kwargs = h.call_args_list[1]
    assert isinstance(args[0], Model)
    assert args[1] == {"ctx": "pre"}


@pytest.mark.asyncio
@pytest.mark.skipif(not mongo_url, reason="Set mongo_url")
async def test_hook_post_delete(ampo_db: AMPODatabase):
    h = AsyncMock()

    class Model(CollectionWorker):
        model_config = ORMConfig(
            orm_collection="test_post_delete",
            orm_hooks={
                "post_delete": [h],
            }
        )
        f1: str

    a = Model(f1="post")
    await a.save()

    # Call #1
    await a.delete()
    h.assert_awaited_once()

    # Call #2 with context
    await a.save()
    await a.delete({"ctx": "post"})
    assert h.await_count == 2
    args, kwargs = h.call_args_list[1]
    assert isinstance(args[0], Model)
    assert args[1] == {"ctx": "post"}
