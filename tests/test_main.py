import os
import unittest
import datetime
from typing import Optional

from bson import ObjectId
from bson.codec_options import CodecOptions
from pydantic import BaseModel, Field, ValidationError

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

    def test_make_database_object(self):
        AMPODatabase.clear()

        a = AMPODatabase(url=mongo_url)
        b = AMPODatabase()
        self.assertEqual(a, b)

    async def test_collectin_01(self):

        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10
            )

            field1: str

        await init_collection()

        # Create instence
        a = A(field1="test")
        self.assertIsNone(a._id)
        self.assertIsNone(a.id)

        # Create instence, second
        await A(field1="test01").save()

        # Save
        await a.save()
        object_id = a._id
        self.assertIsInstance(object_id, ObjectId)
        self.assertIsInstance(a.id, str)

        # update field
        a.field1 = "check"
        await a.save()
        self.assertEqual(object_id, a._id)

        # Get object
        d = await A.get(field1="check")
        self.assertIsInstance(d, A)
        self.assertEqual(d._id, object_id)

        # Get by id
        d = await A.get(_id=object_id)
        self.assertEqual(d._id, object_id)

        # Get by id as str
        d = await A.get(_id=str(object_id))
        self.assertEqual(d._id, object_id)

        # Get all, default
        d = await A.get_all()
        self.assertEqual(len(d), 2)

        # Get all, filter
        d = await A.get_all(filter={"field1": "test01"})
        self.assertEqual(len(d), 1)

        # Get all, filter and sort
        d = await A.get_all(filter={"field1": "test01"}, sort=[("field1", -1)])
        self.assertEqual(len(d), 1)

        # Get all, limit and skip
        d = await A.get_all(filter={"field1": "test01"}, limit=2, skip=1)
        self.assertEqual(len(d), 0)

        # Delete
        d = await A.get(_id=object_id)
        await d.delete()
        d = await A.get_all()
        self.assertEqual(len(d), 1)

    async def test_collectin_02(self):
        """ Check bson options """
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_bson_codec_options=CodecOptions(
                    tz_aware=True
                )
            )

            field1: datetime.datetime

        a = A(field1=datetime.datetime(
            2000, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc))
        await a.save()

        # Get object
        d = await A.get()
        self.assertIsInstance(d, A)
        self.assertEqual(d.field1, a.field1)

    async def test_collectin_03(self):
        """Check revalidate field after create object"""
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                # validate_assignment=False,
            )

            field1: str = Field(max_length=5)

        # Is ok
        A(field1="test")
        # Is not ok
        with self.assertRaises(ValidationError):
            A(field1="test12345")
        # Change field after create object
        a = A(field1="test")
        with self.assertRaises(ValidationError):
            a.field1 = "test12345"

    async def test_collectin_04(self):
        """Check default value in model field"""
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
            )

            field1: str = Field(123)

        with self.assertRaises(ValidationError):
            A()

    async def test_indexes_01(self):
        """
        Simple. One key. Wihtout options
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field1"],
                    }
                ]
            )

            field1: str

        await init_collection()

    async def test_indexes_02(self):
        """
        Multi keys. Without options.
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field1", "field2"],
                    }
                ]
            )

            field1: str
            field2: str

        await init_collection()

    async def test_indexes_04(self):
        """
        Simple. One key. Wiht option unique
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field4"],
                        "options": {
                            "unique": True
                        }
                    }
                ]
            )

            field4: str

        await init_collection()

    async def test_indexes_ttl_05(self):
        """
        One key. With option expireAfterSeconds
        Normal setup
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field5"],
                        "options": {
                            "expireAfterSeconds": 20
                        }
                    }
                ]
            )

            field5: str

        await init_collection()

    async def test_indexes_ttl_06(self):
        """
        One key. With option expireAfterSeconds
        Recreate index with new value expireAfterSeconds
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field6"],
                        "options": {
                            "expireAfterSeconds": 20
                        }
                    }
                ]
            )

            field6: datetime.datetime

        await init_collection()

        # Update raw
        B.expiration_index_update("field6", 10)
        await init_collection()

    async def test_indexes_ttl_07(self):
        """
        One key. With option expireAfterSeconds
        Skip if expireAfterSeconds == -1
        Index don't exist
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field7"],
                        "options": {
                            "expireAfterSeconds": -1
                        }
                    }
                ]
            )

            field7: datetime.datetime

        await init_collection()

        collecton = B._get_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field7_1" not in index_info.keys())

    async def test_indexes_ttl_08(self):
        """
        One key. With option expireAfterSeconds
        Skip if expireAfterSeconds == -1, then set, than set -1 and drop index
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field8"],
                        "options": {
                            "expireAfterSeconds": -1
                        }
                    }
                ]
            )

            field8: datetime.datetime

        collecton = B._get_collection()
        # Skip
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field8_1" not in index_info.keys())
        # set
        B.expiration_index_update("field8", 10)
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field8_1" in index_info.keys())
        # unset -> drop index
        B.expiration_index_update("field8", -1)
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field8_1" not in index_info.keys())

    async def test_indexes_ttl_09(self):
        """
        One key. With option expireAfterSeconds
        Skip create index. Index don't exist
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field9"],
                        "options": {
                            "expireAfterSeconds": 10
                        }
                    }
                ]
            )

            field8: datetime.datetime

        collecton = B._get_collection()

        # Index don't need created
        B.expiration_index_skip("field9")
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field9_1" not in index_info.keys())

    async def test_indexes_ttl_10(self):
        """
        One key. With option expireAfterSeconds
        Index exist. Index don't should be changed
        """
        class B(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
                str_max_length=10,
                orm_indexes=[
                    {
                        "keys": ["field10"],
                        "options": {
                            "expireAfterSeconds": 10
                        }
                    }
                ]
            )

            field8: datetime.datetime

        collecton = B._get_collection()

        # Create
        index_info = await collecton.index_information()
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field10_1" in index_info.keys())

        # Don't change
        B.expiration_index_update("field10", -1)
        B.expiration_index_skip("field10")
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field10_1" in index_info.keys())

        # Second call
        B.expiration_index_skip("field10")
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field10_1" in index_info.keys())

    async def test_relationship_01(self):
        """
        Embeded document
        """
        class CStar(BaseModel):
            name: str

        class C(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",
            )

            field: str
            star: CStar

        # Create instence
        a = C(field="test", star=CStar(name="name"))
        self.assertIsNone(a._id)

        # Save
        await a.save()

        # Get
        d = await C.get(field="test")
        self.assertEqual(d._id, a._id)

    async def test_delete_01(self):
        """
        Delete object, not saved
        """
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test"
            )

            field1: str

        await init_collection()

        # Create instence
        a = A(field1="test")
        self.assertIsNone(a._id)
        with self.assertRaises(ValueError):
            await a.delete()

    async def test_count_01(self):
        """
        Count objects
        """
        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test"
            )
            field1: str

        await init_collection()

        # Check is zero
        self.assertEqual(await A.count(), 0)

        # Add
        await A(field1="test").save()
        await A(field1="abc").save()

        # check total
        self.assertEqual(await A.count(), 2)
        # check filter
        self.assertEqual(await A.count(field1="test"), 1)

    async def test_lock_record_01(self):
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
        a = await A01.get_and_lock(field1="test")
        self.assertIsInstance(a, A01)
        self.assertEqual(a.lfield, True)  # lock is set
        self.assertIsNotNone(a.field_dt_start)  # lock start time is set

        # Not found
        b = await A01.get_and_lock(field1="test")
        self.assertIsNone(b)

        # Unlock
        await a.reset_lock()
        self.assertEqual(a.lfield, False)  # lock is reset

        with self.subTest("check context"):
            async with A01.get_and_lock_context(field1="test") as a:
                self.assertEqual(a.lfield, True)  # lock is set

                # Not found
                b = await A01.get_and_lock(field1="test")
                self.assertIsNone(b)
        self.assertEqual(a.lfield, False)  # lock is unset

    async def test_lock_record_02(self):
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
            await A01.get_and_lock(field1="test")
