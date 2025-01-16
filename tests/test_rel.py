import os
import unittest
import asyncio
import datetime
from typing import List

from bson import ObjectId
from bson.codec_options import CodecOptions
from pydantic import BaseModel, Field, ValidationError

from ampo import (
    AMPODatabase, CollectionWorker, ORMConfig, init_collection, RFManyToMany
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
