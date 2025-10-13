import os
import asyncio
import unittest
import datetime
from typing import Optional

from ampo import AMPODatabase, CollectionWorker, ORMConfig, init_collection
from ampo.utils import datetime_utcnow_tz


mongo_url = os.environ.get("TEST_MONGO_URL", None)

# Check mongo url config
if mongo_url is None:
    raise unittest.SkipTest("Mongo URL is not configured")


class A(CollectionWorker):
    """
    Base class for testing
    """

    model_config = ORMConfig(
        orm_collection="test",
        orm_lock_record={
            "lock_field": "lfield",
            "lock_field_time_start": "lfield_dt_start",
            "lock_max_period_sec": "10"
        }
    )

    field1: str
    lfield: bool = False
    lfield_dt_start: Optional[datetime.datetime] = None


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
        a = await A.get(filter={"field1": "test"})
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

    async def test_get_lock_wait_context_05(self):
        """
        Raise exception when object is locked.
        """

        # Add
        a = A(field1="test")
        await a.save()

        try:
            async with A.get_lock_wait_context(field1="test"):
                # check lock is set
                a = await A.get(filter={"field1": "test"})
                self.assertTrue(a.lfield)

                raise RuntimeError("Object is locked.")
        except Exception:
            pass

        # check lock is removed
        a = await A.get(filter={"field1": "test"})
        self.assertFalse(a.lfield)

    async def test_get_lock_wait_context_06(self):
        """
        Raise exception in corotine when object is locked
        """

        # Add
        a = A(field1="test")
        await a.save()

        async def test():
            raise RuntimeError("Object is locked.")

        try:
            async with A.get_lock_wait_context(field1="test"):
                # check lock is set
                a = await A.get(filter={"field1": "test"})
                self.assertTrue(a.lfield)

                await test()
        except Exception:
            pass

        # check lock is removed
        a = await A.get(filter={"field1": "test"})
        self.assertFalse(a.lfield)

    # get_and_lock

    async def test_get_and_lock_01(self):
        """
        If object locked more than 'dead time', it should be unlocked.
        """
        await init_collection()

        # Add
        a = A(field1="test")
        a.lfield = True
        a.lfield_dt_start = (
            datetime_utcnow_tz() - datetime.timedelta(seconds=20)
        )
        await a.save()
        await asyncio.sleep(0.1)

        # Don't got
        obj = await A.get_and_lock(filter={"field1": "test"})
        self.assertIsInstance(obj, A)

        # Reset lock
        await obj.reset_lock()

        # Get
        obj = await A.get(filter={"field1": "test"})
        self.assertFalse(obj.lfield)

    async def test_get_and_lock_02(self):
        """
        If object locked more than 'dead time'.
        Disable reset lock after 'dead time', lock_max_period_sec=0.
        """
        class A01(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                orm_lock_record={
                    "lock_field": "lfield",
                    "lock_field_time_start": "lfield_dt_start",
                    "lock_max_period_sec": "0"
                }
            )

            field1: str
            lfield: bool = False
            lfield_dt_start: Optional[datetime.datetime] = None

        await init_collection()

        # Add
        a = A01(field1="test")
        a.lfield = True
        a.lfield_dt_start = (
            datetime_utcnow_tz() - datetime.timedelta(seconds=20)
        )
        await a.save()
        await asyncio.sleep(0.1)

        # Don't got
        with self.assertRaises(ValueError) as err:
            obj = await A01.get_and_lock(filter={"field1": "test"})
        self.assertEqual(err.exception.__str__(), "The object is locked")

        # Manual reset lock
        a.lfield = False
        await a.save()

        # Get with lock
        obj = await A01.get_and_lock(filter={"field1": "test"})
        self.assertIsInstance(obj, A01)

    async def test_get_and_lock_03(self):
        """Usage lock_record."""
        class A01(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                orm_lock_record={
                    "lock_field": "lfield",
                    "lock_field_time_start": "field_dt_start",
                }
            )
            field1: str
            lfield: bool = False
            field_dt_start: Optional[datetime.datetime] = None

        await init_collection()

        # Add, lock field is not required
        await A01(field1="test").save()

        # Get lock
        a = await A01.get_and_lock(filter={"field1": "test"})
        self.assertIsInstance(a, A01)
        self.assertEqual(a.lfield, True)  # lock is set
        self.assertIsNotNone(a.field_dt_start)  # lock start time is set

        # Not found
        with self.assertRaises(ValueError):
            b = await A01.get_and_lock(filter={"field1": "test"})

        # Unlock
        await a.reset_lock()
        self.assertEqual(a.lfield, False)  # lock is reset

        with self.subTest("check context"):
            async with A01.get_and_lock_context(field1="test") as a:
                self.assertEqual(a.lfield, True)  # lock is set

                # Not found
                with self.assertRaises(ValueError):
                    b = await A01.get_and_lock(filter={"field1": "test"})
        self.assertEqual(a.lfield, False)  # lock is unset

    async def test_get_and_lock_04(self):
        """Not configured lock_record."""
        class A01(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
            )
            field1: str
            lfield: bool = False
            field_dt_start: Optional[datetime.datetime] = None

        await init_collection()

        with self.assertRaises(ValueError):
            await A01.get_and_lock(filter={"field1": "test"})
