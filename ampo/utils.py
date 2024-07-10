from typing import List, Optional
from datetime import datetime, timezone

from pydantic import ConfigDict, BaseModel, Field
from bson.codec_options import CodecOptions

# Definition
cfg_orm_collection = "orm_collection"
cfg_orm_indexes = "orm_indexes"
cfg_orm_bson_codec_options = "orm_bson_codec_options"
cfg_orm_lock_record = "orm_lock_record"


class ORMIndexOptions(BaseModel):
    unique: Optional[bool] = None
    expireAfterSeconds: Optional[int] = None


class ORMIndex(BaseModel):
    keys: List[str]
    options: Optional[ORMIndexOptions] = None
    skip_initialization: bool = False


class ORMLockRecord(BaseModel):
    """
    Lock record for ORM config

    Field should be add to the model
    """
    lock_field: str = Field(
        ..., description=(
            "Field by which the lock will be acquired. Type: boolean"
        )
    )
    lock_field_time_start: str = Field(
        ...,
        description=(
            "Field which will be contained the start time of the lock. "
            "Type: datetime"
        )
    )


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
    orm_lock_record: Optional[ORMLockRecord]


def datetime_utcnow_tz() -> datetime:
    """Return datetime utc now with timezone"""
    return datetime.now(tz=timezone.utc)
