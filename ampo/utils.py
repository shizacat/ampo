from pydantic import ConfigDict, BaseModel
from typing import List, Optional

# Definition
cfg_orm_collection = "orm_collection"
cfg_orm_indexes = "orm_indexes"


class ORMIndexOptions(BaseModel):
    unique: Optional[bool] = None
    expireAfterSeconds: Optional[int] = None


class ORMIndex(BaseModel):
    keys: List[str]
    options: Optional[ORMIndexOptions] = None


class ORMConfig(ConfigDict):
    """
    Custon configuration for Collection
    """
    # Name of collection
    orm_collection: str
    orm_indexes: List[ORMIndex]
