#!/usr/bin/env python3

"""
Тестирование связанных полей
"""

import asyncio
from typing import Union

from ampo import AMPODatabase, CollectionWorker, ORMConfig, init_collection


class B(CollectionWorker):
    model_config = ORMConfig(
        orm_collection="test_b",
    )
    field2: str


class A(CollectionWorker):
    model_config = ORMConfig(
        orm_collection="test",
    )
    field: str
    b: B


async def main():
    AMPODatabase(url="mongodb://localhost:27017/test1")
    await init_collection()

    a = A(field="test", b=B(field2="test123"))
    await a.save()
    print(await A.get())


if __name__ == "__main__":
    asyncio.run(main())
