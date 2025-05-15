# Aio Mongo Pydantic ORM (ampo)

Features:
- The ORM is based on pydantic
- Asynchronous
- Many to many relationships
- One to many relationships
- Support MongoDB from 4.2
- Python 3.8+


# Usage

All example run into:

```bash
python -m asyncio
```

## Create and get object

```python
from ampo import CollectionWorker, AMPODatabase, ORMConfig, init_collection

# Initilize DB before calls db methods
AMPODatabase(url="mongodb://test")

# Pydantic Model
class ModelA(CollectionWorker):
    field1: str
    field2: int

    model_config = ORMConfig(
        orm_collection="test"
    )

await init_collection()

inst_a = ModelA("test", 123)
await inst_a.save()

# Get object
inst_a = await ModelA.get(field1="test")
```

## Get all objects

Support additional options for this method. See [find()](https://pymongo.readthedocs.io/en/stable/api/pymongo/collection.html#pymongo.collection.Collection.find).

Example:
```python
from ampo import CollectionWorker, AMPODatabase, ORMConfig, init_collection

# Initilize DB before calls db methods
AMPODatabase(url="mongodb://test")

# Pydantic Model
class ModelA(CollectionWorker):
    field1: str
    field2: int
    
    model_config = ORMConfig(
        orm_collection="test"
    )

await init_collection()

inst_a = ModelA("test", 123)
await inst_a.save()

# Get all objects
insts = await ModelA.get_all()

# Get all objects, by filter, and addional options
insts = await ModelA.get_all(
    filter={"field1": "test"},
    sort=[("field2", 1)],
    limit=10,
    skip=0
)
```

## Id

For search by 'id' usages in filter '_id' or 'id' name.

For type ObjectId, use 'PydanticObjectId'.

Example:
```python
from bson.objectid import ObjectId
from ampo import (
    CollectionWorker,
    AMPODatabase,
    ORMConfig,
    init_collection,
    PydanticObjectId
)


# Initilize DB before calls db methods
AMPODatabase(url="mongodb://test")

# Pydantic Model
class ModelA(CollectionWorker):
    field1: PydanticObjectId
    
    model_config = ORMConfig(orm_collection="test")

await init_collection()

inst_a = ModelA(field1=ObjectId("63538168e94461001215836a"))
await inst_a.save()
```

## Indexes

```python
# import

# Initilize DB before calls db methods
AMPODatabase(url="mongodb://test")

# Pydantic Model
class ModelA(CollectionWorker):
    field1: str

    model_config = ORMConfig(
        orm_collection="test",
        orm_indexes=[
            {
                "keys": ["field1"],
                "options": {
                    "unique": True
                }
            }
        ]
    )

# This method create indexes
# Call only one time
await init_collection()
```

Suppport options:
  - unique
  - expireAfterSeconds

Keys is list of fields.

### TTL Index
 
It works only with single field ([TTL Indexes](https://www.mongodb.com/docs/manual/core/index-ttl/#ttl-indexes)).
 
You should set the option 'expireAfterSeconds', and field 'keys' should have only single field.

Example:

```python
# import

# Initilize DB before calls db methods
AMPODatabase(url="mongodb://test")

# Pydantic Model
class ModelA(CollectionWorker):
    field1: datetime

    model_config = ORMConfig(
        orm_collection="test",
        orm_indexes=[
            {
                "keys": ["field1"],
                "options": {
                    "expireAfterSeconds": 10
                }
            }
        ]
    )

# optional, set new value
ModelA.update_expiration_value("field1", 20)

await init_collection()
```

if you want to set the 'expireAfterSeconds' only from method 'update_expiration_value', set it to '-1'.
if you want skip the index changed, call method 'expiration_index_skip' before init_collection.

### Indexes in replica set cluster

The replica set cluster has a specific behavior when creating indexes.
If one of the nodes in the cluster is not reachable, the index creation will wait for the node to become available.
See [Index Builds in Replicated Environments](https://www.mongodb.com/docs/manual/core/index-creation/#index-builds-in-replicated-environments).
Change this behavior by setting the 'commit_quorum' option to 'majority'. See [createIndexes](https://www.mongodb.com/docs/manual/reference/method/db.collection.createIndex/#std-label-createIndex-method-commitQuorum).

Supported only from MongoDB version 4.4.

Example:

```python
# import

# Initilize DB before calls db methods
AMPODatabase(url="mongodb://test")

# Pydantic Model
class ModelA(CollectionWorker):
    field1: str

    model_config = ORMConfig(
        orm_collection="test",
        orm_indexes=[
            {
                "keys": ["field1"],
                "commit_quorum": "majority",
            }
        ]
    )

await init_collection()
```

## Relationships between documents

### Embeded

It is supported by default. Just, you need create the embedded document as class of pydantic - 'BaseModel'. It will be stored into db as object.

Example:
```python
from pydantic import BaseModel

class Embeded(BaseModel):
    name: str

class ModelA(CollectionWorker):
    field1: str
    field2: Embeded

    model_config = ORMConfig(
        orm_collection="test"
    )
```

## Lock Record

It is a mechanism that allows you to retrieve a record with a lock. It is based on the [findOneAndUpdate()](https://www.mongodb.com/docs/manual/reference/method/db.collection.findOneAndUpdate/). When the record is found, the field "lock_field" is set to True. And when the next search is made, this record will be skipped.

Example:

```python
import datetime
from typing import Optional
from ampo import CollectionWorker, AMPODatabase, ORMConfig, init_collection

# Pydantic Model
class ModelA(CollectionWorker):
    field1: str
    lfield: bool = False
    field_dt_start: Optional[datetime.datetime] = None

    model_config = ORMConfig(
        orm_collection="test",
        orm_lock_record={
            "lock_field": "lfield",
            "lock_field_time_start": "field_dt_start",
        }
    )

await init_collection()

inst_a = ModelA("test", 123)
await inst_a.save()

inst_a = await ModelA.get_and_lock(field1="test")
# process
await inst_a.reset_lock()

# as context
async with ModelA.get_and_lock_context(field1="test") as inst_a:
    pass
    # process

# as context, version II
# timeout on wait
try:
  async with ModelA.get_lock_wait_context(
      filter={"field1": "test"}, timeout=10
  ) as inst_a:
      pass
except (TimeoutError, ValueError) as e:
    print("Error:", e)
```

Mehanism reset lock.
If lock exist more than time, set 'lock_max_period_sec', lock will be reset.
Default value is 15 minutes.

## Hooks

Example:
```python
import datetime
from typing import Optional
from ampo import CollectionWorker, AMPODatabase, ORMConfig, init_collection

# hooks
await def hook(obj, context: dict):
    print("Call hook for", obj)

# Pydantic Model
class ModelA(CollectionWorker):
    field1: str

    model_config = ORMConfig(
        orm_collection="test",
        orm_hooks={
            "pre_save": [hook],
            "post_save": [],
            "pre_delete": [],
            "post_delete": [],
        }
    )

a = ModelA(field1="test")
await a.save(context={"any": "any"})
```

# Development

Style:
- [NumPy/SciPy docstrings style guide](https://numpydoc.readthedocs.io/en/latest/format.html)

Run tests:

```bash
env TEST_MONGO_URL=mongodb://localhost/test pytest
```