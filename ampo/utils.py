import sys
import asyncio
import logging
from typing import List, Optional, Union, Callable, Awaitable, Any
from datetime import datetime, timezone
from enum import Enum

from pydantic import ConfigDict, BaseModel, Field
from bson.codec_options import CodecOptions

# Definition
cfg_orm_collection = "orm_collection"
cfg_orm_indexes = "orm_indexes"
cfg_orm_bson_codec_options = "orm_bson_codec_options"
cfg_orm_lock_record = "orm_lock_record"
cfg_orm_hooks = "orm_hooks"

# For Python 3.9+ uses TypeAlias
if sys.version_info >= (3, 9):
    from typing_extensions import TypeAlias

    # TODO: Any it is CollectionWorker, but how correct it setup
    HookType: TypeAlias = Callable[
        [Any, Optional[dict]], Awaitable[None]
    ]
else:
    HookType = Callable[[Any, Optional[dict]], Awaitable[None]]


class commitQuorum(str, Enum):
    """
    Quorum for commit
    """

    VOTING_MEMBERS = "votingMembers"
    MAJORITY = "majority"


class ORMIndexOptions(BaseModel):
    unique: Optional[bool] = None
    expireAfterSeconds: Optional[int] = None


class ORMIndex(BaseModel):
    keys: List[str]
    options: Optional[ORMIndexOptions] = None
    skip_initialization: bool = False
    commit_quorum: Optional[Union[commitQuorum, int]] = None

    @property
    def commit_quorum_value(self) -> Optional[Union[int, str]]:
        """
        Return value of commit quorum
        """
        if self.commit_quorum is None:
            return
        if isinstance(self.commit_quorum, int):
            return self.commit_quorum
        return self.commit_quorum.value


class ORMLockRecord(BaseModel):
    """
    Lock record for ORM config

    Field should be add to the model
    """

    lock_field: str = Field(
        ...,
        description=("Field by which the lock will be acquired. Type: boolean"),
    )
    lock_field_time_start: str = Field(
        ...,
        description=(
            "Field which will be contained the start time of the lock. "
            "Type: datetime"
        ),
    )
    lock_max_period_sec: int = Field(
        15 * 60,
        description=(
            "The maximum period of time for which the lock will be acquired. "
            "If '0' - the lock will be acquired until the end of the process. "
            "Type: int"
        ),
    )


class ORMHooks(BaseModel):
    """
    Hooks for ORM
    """

    pre_save: List[HookType] = Field(default_factory=list)
    post_save: List[HookType] = Field(default_factory=list)
    pre_delete: List[HookType] = Field(default_factory=list)
    post_delete: List[HookType] = Field(default_factory=list)


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
    orm_hooks: Optional[ORMHooks]


def datetime_utcnow_tz() -> datetime:
    """Return datetime utc now with timezone"""
    return datetime.now(tz=timezone.utc)


async def period_check_future(
    aws: asyncio.Future,
    period: float = 20.0,
    msg: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
):
    """
    Periodic check awaitables

    Args:
        aws - awaitable
        period - Period of checking, in seconds
        msg - Message for logger
        logger - Logger
    """
    # configure logger
    if logger is None:
        logger = logging.getLogger(__name__)
    if msg is None:
        msg = f"Periodic check, running '{aws}' ..."

    while True:
        try:
            await asyncio.wait([aws], timeout=period)
        except asyncio.TimeoutError:
            pass
        if aws.done():
            break
        logger.info(msg)
