# Aio Mongo Pydantic ORM (ampo)

Features:
- Asyncronous

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

# Development

Style:
- [NumPy/SciPy docstrings style guide](https://numpydoc.readthedocs.io/en/latest/format.html)
