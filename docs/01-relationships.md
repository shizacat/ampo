# Relationships

## Many to Many

Example:

```python
from ampo import (
    CollectionWorker,
    AMPODatabase,
    ORMConfig,
    init_collection,
    RFManyToMany
)

# Initilize DB before calls db methods
AMPODatabase(url="mongodb://test")

# Pydantic Model
class ModelCity(CollectionWorker):
    name: str

    model_config = ORMConfig(
        orm_collection="city"
    )

class ModelA(CollectionWorker):
    field1: str
    cities: RFManyToMany[ModelCity]

    model_config = ORMConfig(
        orm_collection="test"
    )

await init_collection()

# Add city
c01 = ModelCity(name="city-01")
await c01.save()

# Add A
inst_a = ModelA(field1="test")
inst_a.cities.append(c01)
await inst_a.save()

# Get object
inst_a = await ModelA.get(field1="test")
```

## One to Many

Example:
```python
from ampo import (
    CollectionWorker,
    AMPODatabase,
    ORMConfig,
    init_collection,
    RFOneToMany
)

# Initilize DB before calls db methods
AMPODatabase(url="mongodb://test")

# Pydantic Model
class ModelCity(CollectionWorker):
    name: str

    model_config = ORMConfig(
        orm_collection="city"
    )

class ModelA(CollectionWorker):
    field1: str
    city: RFOneToMany[ModelCity]

    model_config = ORMConfig(
        orm_collection="test"
    )

# Add city
c01 = ModelCity(name="city-01")
await c01.save()

# Add A
inst_a = ModelA(field1="test", city=c01)
await inst_a.save()

# Get object
inst_a = await ModelA.get(field1="test")
```
