from typing import List, Optional

from pydantic import ConfigDict, BaseModel
from bson.codec_options import CodecOptions

# Definition
cfg_orm_collection = "orm_collection"
cfg_orm_indexes = "orm_indexes"
cfg_orm_bson_codec_options = "orm_bson_codec_options"


class ORMIndexOptions(BaseModel):
    unique: Optional[bool] = None
    expireAfterSeconds: Optional[int] = None


class ORMIndex(BaseModel):
    keys: List[str]
    options: Optional[ORMIndexOptions] = None


class ORMConfig(ConfigDict):
    """
    Custon configuration for Collection

    orm_collection - Name of collection for this object
    orm_indexes - The list of indexes, what it will be set on mongo collection
    orm_bson_codec_options - This options will apply on the collection
        every time, when the collection is returned
    """
    # Name of collection
    orm_collection: str
    orm_indexes: List[ORMIndex]
    orm_bson_codec_options: Optional[CodecOptions]
