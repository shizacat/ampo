import os
import asyncio
import unittest
import datetime

from bson import ObjectId
from bson.codec_options import CodecOptions
from pydantic import ConfigDict, BaseModel

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

        # Save
        await a.save()
        object_id = a._id
        self.assertIsInstance(object_id, ObjectId)

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

        # Get all
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

    async def test_indexes_05(self):
        """
        Simple. One key. Wiht option expireAfterSeconds
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

    async def test_indexes_06(self):
        """
        Simple. One key. With option expireAfterSeconds
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
        B.update_expiration_value("field6", 10)
        await init_collection()

    async def test_indexes_07(self):
        """
        Simple. One key. With option expireAfterSeconds
        Skip if expireAfterSeconds == -1
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

    async def test_indexes_08(self):
        """
        Simple. One key. With option expireAfterSeconds
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
        B.update_expiration_value("field8", 10)
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field8_1" in index_info.keys())
        # unset -> drop index
        B.update_expiration_value("field8", -1)
        await init_collection()
        index_info = await collecton.index_information()
        self.assertTrue("field8_1" not in index_info.keys())

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
