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

# Development

Style:
- [NumPy/SciPy docstrings style guide](https://numpydoc.readthedocs.io/en/latest/format.html)

Run tests:

```bash
env TEST_MONGO_URL=mongodb://localhost/test pytest
```