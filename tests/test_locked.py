import os
import asyncio
import unittest
import datetime
from typing import Optional

from ampo import AMPODatabase, CollectionWorker, ORMConfig, init_collection


mongo_url = os.environ.get("TEST_MONGO_URL", None)

# Check mongo url config
if mongo_url is None:
    raise unittest.SkipTest("Mongo URL is not configured")


class Main(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        db = AMPODatabase(url=mongo_url)
        await db._client.drop_database(db._client.get_default_database())
        # await asyncio.sleep(0.4)
        return await super().asyncSetUp()

    async def asyncTearDown(self) -> None:
        AMPODatabase.clear()

        return await super().asyncTearDown()

    async def test_get_lock_wait_context_01(self):
        """
        Simple work
        """
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                orm_lock_record={
                    "lock_field": "lfield",
                    "lock_field_time_start": "lfield_dt_start",
                }
            )

            field1: str
            lfield: bool = False
            lfield_dt_start: Optional[datetime.datetime] = None

        await init_collection()

        # Add
        await A(field1="test").save()

        # Get and lock
        async with A.get_lock_wait_context(filter={"field1": "test"}) as a:
            a: A
            self.assertEqual(a.field1, "test")
            self.assertTrue(a.lfield)
        # Check lock is removed
        a = await A.get(field1="test")
        self.assertFalse(a.lfield)

    async def test_get_lock_wait_context_02(self):
        """
        Get locked object, wait until timeout
        """
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                orm_lock_record={
                    "lock_field": "lfield",
                    "lock_field_time_start": "lfield_dt_start",
                }
            )

            field1: str
            lfield: bool = False
            lfield_dt_start: Optional[datetime.datetime] = None

        await init_collection()

        # Add
        await A(field1="test").save()

        # Get and lock
        async with A.get_lock_wait_context(
            filter={"field1": "test"}
        ):
            with self.assertRaises(asyncio.TimeoutError):
                async with A.get_lock_wait_context(
                    filter={"field1": "test"}, timeout=0.1
                ):
                    pass

    async def test_get_lock_wait_context_03(self):
        """
        The object don't exist
        """
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                orm_lock_record={
                    "lock_field": "lfield",
                    "lock_field_time_start": "lfield_dt_start",
                }
            )

            field1: str
            lfield: bool = False
            lfield_dt_start: Optional[datetime.datetime] = None

        await init_collection()

        # Add
        await A(field1="test").save()

        # Get and lock
        with self.assertRaises(ValueError):
            async with A.get_lock_wait_context(
                filter={"field1": "aaa"}
            ):
                pass

    async def test_get_lock_wait_context_04(self):
        """
        Get locked object,
        - locked other function
        - release
        - end wait and get object
        """
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                orm_lock_record={
                    "lock_field": "lfield",
                    "lock_field_time_start": "lfield_dt_start",
                }
            )

            field1: str
            lfield: bool = False
            lfield_dt_start: Optional[datetime.datetime] = None

        await init_collection()

        # Add
        await A(field1="test").save()

        async def lock():
            async with A.get_lock_wait_context(
                filter={"field1": "test"}
            ):
                await asyncio.sleep(1)

        t = asyncio.create_task(lock())
        await asyncio.sleep(0.1)

        # Get and lock
        async with A.get_lock_wait_context(
            filter={"field1": "test"}, timeout=2
        ):
            self.assertTrue(t.done())
