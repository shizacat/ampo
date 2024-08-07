# Aio Mongo Pydantic ORM (ampo)

Features:
- Asynchronous

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

## Id

For search by 'id' usages in filter '_id' or 'id' name.

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
```

# Development

Style:
- [NumPy/SciPy docstrings style guide](https://numpydoc.readthedocs.io/en/latest/format.html)

Run tests:

```bash
env TEST_MONGO_URL=mongodb://localhost/test pytest
```