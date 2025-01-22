import os
import unittest
import asyncio
import datetime
from typing import List

from bson import ObjectId
from bson.codec_options import CodecOptions
from pydantic import BaseModel, Field, ValidationError

from ampo import (
    AMPODatabase,
    CollectionWorker,
    ORMConfig,
    init_collection,
    RFManyToMany,
    RFOneToMany,
)


mongo_url = os.environ.get("TEST_MONGO_URL", None)

# Check mongo url config
if mongo_url is None:
    raise unittest.SkipTest("Mongo URL is not configured")


class R1(CollectionWorker):
    """Base"""
    model_config = ORMConfig(
        orm_collection="test-relation-mtm-01-r1",
    )
    name: str


class A(CollectionWorker):
    """Base"""
    model_config = ORMConfig(
        orm_collection="test-relation-mtm-01-a",
    )

    field1: str
    names: RFManyToMany[R1]
    t: List[int] = Field(default_factory=list)


class Main(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        db = AMPODatabase(url=mongo_url)
        await db._client.drop_database(db._client.get_default_database())
        return await super().asyncSetUp()

    async def asyncTearDown(self) -> None:
        AMPODatabase.clear()

        return await super().asyncTearDown()

    async def test_relation_mtm_01(self):
        """
        Variants of usage ManyToMany, success
        """
        await init_collection()

        # Create with empty list
        a = A(field1="test")
        self.assertIsInstance(a, A)
        self.assertEqual(len(a.names), 0)

        # Create with element
        a = A(field1="test", names=[R1(name="test")])
        self.assertIsInstance(a, A)
        self.assertEqual(len(a.names), 1)

        # Check model_dump, correct field exists
        a = A(field1="test", names=[R1(name="test")])
        d = a.model_dump(skip_save_check=True)
        self.assertIn("names_ids", d)
        self.assertNotIn("names", d)

        # Check model_dump, except if the object don't save
        a = A(field1="test", names=[R1(name="test")])
        with self.assertRaises(ValueError):
            a.model_dump()

    async def test_relation_mtm_02(self):
        """
        Success create
        """
        await init_collection()

        r = R1(name="test")
        await r.save()

        # Create with empty list
        a = A(field1="test0")
        await a.save()
        # __ get and check
        a1 = await A.get(id=a.id)
        self.assertEqual(len(a1.names), 0)

        # Create with element
        a = A(field1="test1", names=[r])
        await a.save()
        # __ get and check
        a1 = await A.get(id=a.id)
        self.assertEqual(len(a1.names), 1)
        self.assertEqual(a1.names[0].name, "test")

        # Create and add element
        a = A(field1="test2")
        a.names.append(r)
        await a.save()
        # __ get and check
        a1 = await A.get(id=a.id)
        self.assertEqual(len(a1.names), 1)
        self.assertEqual(a1.names[0].name, "test")

    async def test_relation_mtm_03(self):
        """
        Success create with many elements
        """
        class R2(CollectionWorker):
            """Base"""
            model_config = ORMConfig(
                orm_collection="test-relation-mtm-r-03",
            )
            data: str
            names: RFManyToMany[R1]

        class A1(CollectionWorker):
            """Base"""
            model_config = ORMConfig(
                orm_collection="test-relation-mtm-a-03",
            )
            field1: str
            datas: RFManyToMany[R2]

        await init_collection()

        r = R1(name="name-test")
        await r.save()

        r2 = R2(data="data-test", names=[r])
        await r2.save()

        a = A1(field1="test", datas=[r2])
        await a.save()

        # __ get and check
        a1 = await A1.get(id=a.id)
        self.assertEqual(len(a1.datas), 1)
        self.assertEqual(a1.datas[0].data, "data-test")
        self.assertEqual(len(a1.datas[0].names), 1)
        self.assertEqual(a1.datas[0].names[0].name, "name-test")

    async def test_relation_mtm_04(self):
        """
        Success get through the method 'get_all'
        """
        await init_collection()

        # Create and fill db
        r = R1(name="rrr-test")
        await r.save()
        a = A(field1="test", names=[r])
        await a.save()

        # Get all
        a_all = await A.get_all()
        self.assertEqual(len(a_all), 1)
        self.assertEqual(len(a_all[0].names), 1)
        self.assertEqual(a_all[0].names[0].name, "rrr-test")

    # --- One To Many ---

    async def test_relation_otm_01(self):
        """
        Success create
        """
        class A1(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test-relation-otm-01",
            )
            field1: str
            name: RFOneToMany[R1]

        # Create with empty
        a = A1(field1="test")
        self.assertIsNone(a.name)

        # Create with element
        a = A1(field1="test", name=R1(name="test"))
        self.assertIsInstance(a.name, CollectionWorker)

        # Except, create wrong type
        with self.assertRaises(ValueError):
            a = A1(field1="test", name=123)

        # Except, set wrong type
        with self.assertRaises(ValueError):
            a = A1(field1="test")
            a.name = 123

        # Model dump, correct field exists
        a = A1(field1="test", name=R1(name="test"))
        d = a.model_dump(skip_save_check=True)
        self.assertIn("name_id", d)
        self.assertNotIn("name", d)

        # Model dump, except if the object don't save
        a = A1(field1="test", name=R1(name="test"))
        with self.assertRaises(ValueError):
            a.model_dump()

    async def test_relation_otm_02(self):
        """
        Success, save and get
        """
        class A2(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test-relation-otm-02",
            )
            field1: str
            name: RFOneToMany[R1]

        await init_collection()

        # Create
        r = R1(name="rrr-test")
        await r.save()
        a = A2(field1="test", name=r)
        await a.save()

        # __ get and check
        a1 = await A2.get(id=a.id)
        self.assertEqual(a1.name.name, "rrr-test")

        # __ get all
        a_all = await A2.get_all()
        self.assertEqual(len(a_all), 1)
        self.assertEqual(a_all[0].name.name, "rrr-test")

    async def test_relation_otm_03(self):
        """
        Success, save without field
        """
        class A3(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test-relation-otm-03",
            )
            field1: str
            name: RFOneToMany[R1]

        await init_collection()

        a = A3(field1="test")
        await a.save()

        a1 = await A3.get(id=a.id)
        self.assertEqual(a1.field1, "test")
        self.assertIsNone(a1.name)

        r = R1(name="rrr-test")
        await r.save()
        a1.name = r
        await a1.save()

        a1_updated = await A3.get(id=a1.id)
        self.assertEqual(a1_updated.name.name, "rrr-test")

        # __ get all
        a_all = await A3.get_all()
        self.assertEqual(len(a_all), 1)
        self.assertEqual(a_all[0].name.name, "rrr-test")
