import os
import unittest
import datetime
from typing import List

from bson import ObjectId
from bson.codec_options import CodecOptions
from pydantic import BaseModel, Field, ValidationError

from ampo import AMPODatabase, CollectionWorker, ORMConfig, init_collection
from ampo.worker import RFManyToMany


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

    async def test_relation_mtm_01(self):
        """
        Variants of usage ManyToMany, success
        """
        class R1(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test-relation-mtm-01",
            )
            name: str

        class A(CollectionWorker):
            model_config = ORMConfig(
                orm_collection="test",

                # template
                # arbitrary_types_allowed=True,
            )

            field1: str
            names: RFManyToMany[R1]
            t: List[int] = Field(default_factory=list)

        await init_collection()

        r = R1(name="test")
        a = A(field1="test", names=[r])
        self.assertEqual(len(a.names), 1)
        print(a)
        print(a.model_dump())

        b = A(field1="test")
        self.assertEqual(len(b.names), 0)
