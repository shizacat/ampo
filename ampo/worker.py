import asyncio
import copy
import typing
from contextlib import asynccontextmanager
import datetime
from typing import (
    Optional,
    TypeVar,
    Type,
    List,
    Tuple,
    AsyncIterator,
    get_origin,
    get_args,
)
from typing_extensions import Annotated, TypeAliasType
import sys

import bson.son
from bson import ObjectId
from motor import motor_asyncio
from pydantic import BaseModel, Field
from pymongo import IndexModel, ReturnDocument

from .db import AMPODatabase
from .utils import (
    ORMIndex,
    ORMLockRecord,
    cfg_orm_collection,
    cfg_orm_indexes,
    cfg_orm_bson_codec_options,
    cfg_orm_lock_record,
    datetime_utcnow_tz,
    period_check_future,
)
from .log import logger


T = TypeVar("T", bound="CollectionWorker")

# For Python 3.9+ uses TypeAlias
if sys.version_info >= (3, 9):
    RFManyToMany = Annotated[
        List[T], Field(default_factory=list, title="RFManyToMany")
    ]
else:
    RFManyToMany = TypeAliasType(
        "RFManyToMany",
        Annotated[List[T], Field(default_factory=list)],
        # type_params=(T,),
    )


class CollectionWorker(
    BaseModel,
    # Config default model, from metaclass
    validate_assignment=True,
    validate_default=True,
):
    """
    Base class for working with collections as pydatnic models
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Internal variable
        self._id: Optional[ObjectId] = None

    async def save(self):
        """
        Save object to db.
        If the object exists into db, then the object will be replace.
        This is will checked by '_id' field.
        """
        collection = self._get_collection()

        if self._id is None:
            # insert
            result = await collection.insert_one(self.model_dump())
            self._id = result.inserted_id
            return

        # update
        await collection.replace_one({"_id": self._id}, self.model_dump())
        # TODO: Not shure what better
        # await collection.update_one(
        #     {"_id": self._id}, {"$set": self.model_dump()}, upsert=False)

    @classmethod
    async def get(cls: Type[T], **kwargs) -> Optional[T]:
        """
        Get one object from database
        """
        collection = cls._get_collection()

        data = await collection.find_one(
            filter=CollectionWorker._prepea_filter_get(kwargs)
        )
        if data is None:
            return
        await cls._rel_get_data(data)
        return cls._create_obj(data)

    @classmethod
    async def get_all(
        cls: Type[T], filter: Optional[dict] = None, **kwargs
    ) -> List[T]:
        """
        Search all object by filter.

        Parameters analogous from the library pymongo:
        https://pymongo.readthedocs.io/en/4.9/api/pymongo/collection.html#pymongo.collection.Collection.find

        Args:
            filter (dict): filter for search
        """
        result = []

        collection = cls._get_collection()

        data = await collection.find(
            filter=CollectionWorker._prepea_filter_get(filter), **kwargs
        ).to_list(None)
        for d in data:
            await cls._rel_get_data(d)
            result.append(cls._create_obj(d))
        return result

    async def delete(self):
        """
        Delete object from database
        """
        collection = self._get_collection()
        if self._id is None:
            raise ValueError("Object not created")
        await collection.delete_one({"_id": self._id})

    @classmethod
    async def count(cls: Type[T], **kwargs) -> int:
        """Return count of objects"""
        return await cls._get_collection().count_documents(
            CollectionWorker._prepea_filter_get(kwargs)
        )

    @classmethod
    async def exists(cls: Type[T], **kwargs) -> bool:
        """Return True if exists object"""
        return await cls.count(**kwargs) > 0

    @classmethod
    async def get_and_lock(cls: Type[T], **kwargs: dict) -> Optional[T]:
        """Get and lock"""
        cfg_lock_record = cls._get_cfg_lock_record()
        l_dt_start = datetime_utcnow_tz()

        # Create filter
        filter = CollectionWorker._prepea_filter_get(kwargs)
        if cfg_lock_record.lock_max_period_sec > 0:
            filter.update(
                {
                    "$or": [
                        {cfg_lock_record.lock_field: False},
                        {
                            cfg_lock_record.lock_field: True,
                            cfg_lock_record.lock_field_time_start: {
                                "$lt": l_dt_start
                                - datetime.timedelta(
                                    seconds=cfg_lock_record.lock_max_period_sec
                                )
                            },
                        },
                    ]
                }
            )
        else:
            filter.update({cfg_lock_record.lock_field: False})

        # Get
        data: Optional[dict] = await cls._get_collection().find_one_and_update(
            filter=filter,
            update={
                "$set": {
                    cfg_lock_record.lock_field: True,
                    cfg_lock_record.lock_field_time_start: l_dt_start,
                }
            },
            return_document=(
                ReturnDocument.BEFORE
                if cfg_lock_record.lock_max_period_sec > 0
                else ReturnDocument.AFTER
            ),
        )
        if data is None:
            return

        # Check
        if cfg_lock_record.lock_max_period_sec > 0:
            data_obj = cls._create_obj(data)
            data_l_dt_start: datetime.datetime = getattr(
                data_obj, cfg_lock_record.lock_field_time_start
            )
            if data_l_dt_start is not None:
                # Ensure TZ is UTC
                data_l_dt_start = data_l_dt_start.replace(
                    tzinfo=datetime.timezone.utc
                )
                if l_dt_start - data_l_dt_start > datetime.timedelta(
                    seconds=cfg_lock_record.lock_max_period_sec
                ):
                    logger.warning(
                        "Lock is expired. "
                        f"ObjectID: {data_obj.id}. "
                        f"Lock time start: {data_l_dt_start}."
                    )
            # Get original data
            data = await cls._get_collection().find_one(
                filter=CollectionWorker._prepea_filter_get(kwargs)
            )
            if data is None:
                raise RuntimeError("Object not found")

        # Create object
        await cls._rel_get_data(data)
        return cls._create_obj(data)

    async def reset_lock(self):
        """Reset lock"""
        # check lock-record is enabled
        cfg_lock_record = self._get_cfg_lock_record()
        # check object is saved
        if self._id is None:
            raise ValueError("Not saved")

        # update field
        setattr(self, cfg_lock_record.lock_field, False)

        # update document
        await self._get_collection().update_one(
            filter=CollectionWorker._prepea_filter_get({"_id": self._id}),
            update={
                "$set": {
                    cfg_lock_record.lock_field: getattr(
                        self, cfg_lock_record.lock_field
                    )
                }
            },
        )

    @classmethod
    @asynccontextmanager
    async def get_and_lock_context(
        cls: Type[T], **kwargs: dict
    ) -> AsyncIterator[T]:
        """Get and lock context"""
        obj = await cls.get_and_lock(**kwargs)
        try:
            yield obj
        finally:
            if obj is not None:
                await obj.reset_lock()

    @classmethod
    @asynccontextmanager
    async def get_lock_wait_context(
        cls: Type[T], filter: dict, timeout: float = 5
    ):
        """
        Get object if it is not locked, otherwise wait until it is unlocked

        Work without transaction.

        Args:
            filter - filter for search the object
            timeout - timeout in seconds, 0 wait forever

        Raises:
            ValueError
            asyncio.TimeoutError
        """
        loop = asyncio.get_running_loop()

        int_up = 0.5  # check every 0.5 seconds
        is_try = False
        time_start = loop.time()

        while True:
            # Wait
            if is_try:
                if timeout != 0 and loop.time() - time_start > timeout:
                    raise asyncio.TimeoutError()
                await asyncio.sleep(int_up)
            else:
                is_try = True

            # Check the object is exists
            obj = await cls.exists(**filter)
            if not obj:
                raise ValueError("The object not found")

            obj = await cls.get_and_lock(**filter)
            if obj is None:
                continue
            break

        # The object is got and locked
        try:
            yield obj
        finally:
            if obj is not None:
                await obj.reset_lock()

    @classmethod
    def expiration_index_update(cls: Type[T], field: str, expire_seconds: int):
        """Update expire index for collections by field name

        Parameters
        ----------
        field : str
            Name of field, for which value expire will be changed
        expire_seconds : int
            New value of expireAfterSeconds, in second
        """
        for index in cls.model_config.get(cfg_orm_indexes, []):
            keys = index.get("keys", [])
            if len(keys) != 1 or keys[0] != field:
                continue
            index["options"]["expireAfterSeconds"] = expire_seconds
            return
        raise ValueError(f"The index by '{field}' not found")

    @classmethod
    def expiration_index_skip(cls: Type[T], field: str):
        """Skip index for collections by field name

        Parameters
        ----------
        field : str
            Name of field, for which index will be skipped
        """
        indexes = cls.model_config.get(cfg_orm_indexes, [])
        for i, index in enumerate(indexes):
            keys = index.get("keys", [])
            if len(keys) != 1 or keys[0] != field:
                continue
            index["skip_initialization"] = True
            return
        raise ValueError(f"The index by '{field}' not found")

    def model_dump(
        self,
        *args,
        as_origin: bool = False,
        skip_save_check: bool = False,
        **kwargs,
    ) -> dict:
        """
        Return dict with data for save in database

        Args:
            as_origin - return dict with original data
            skip_save_check - exclude the mtm fields that are not saved
        """
        if as_origin:
            return super().model_dump(*args, **kwargs)

        if "exclude" not in kwargs:
            kwargs["exclude"] = []

        # MtM exclude
        kwargs["exclude"].extend([x for x, _ in self._mtm_get_fields()])

        data = super().model_dump(*args, **kwargs)

        # MtM add fields
        for fname, ftype in self._mtm_get_fields():
            mtm_field_name = self._mtm_field_name(fname)
            data[mtm_field_name] = []
            for mtm_obj in getattr(self, fname):
                assert isinstance(mtm_obj, CollectionWorker)
                if mtm_obj._id is None:
                    if skip_save_check:
                        continue
                    raise ValueError(
                        f"The one or more objects in the field '{fname}' "
                        "is not saved"
                    )
                data[mtm_field_name].append(mtm_obj._id)

        return data

    # __ Properties ___

    @property
    def id(self) -> Optional[str]:
        """
        Return id of object
        """
        if self._id is None:
            return
        return str(self._id)

    # ___ Private methods ___

    @classmethod
    def _mtm_get_fields(cls) -> List[Tuple[str, str]]:
        """
        Return list of fields for many-to-many relations

        For Python 3.12+ ftype is:
            typing.Annotated[typing.List[<T>]
        """
        result = []
        for fname, ftype in cls.__annotations__.items():
            if sys.version_info >= (3, 9):
                if (
                    get_origin(ftype) == typing.Annotated
                    and cls._annotated_get_title(ftype)
                    == RFManyToMany.__metadata__[0].title
                ):
                    result.append((fname, ftype))
            else:
                if get_origin(ftype) == RFManyToMany:
                    result.append((fname, ftype))
        return result

    @classmethod
    def _mtm_field_name(cls, mtm_filed_name: str) -> str:
        """
        Generate name of field for many-to-many relations
        which will be used for save in database
        """
        mtm_suffix = "_ids"
        return f"{mtm_filed_name}{mtm_suffix}"

    @classmethod
    async def _rel_get_data(cls, data: dict):
        """
        Added to the data relation fields (mtm)

        Args:
            data - dict with data of parent, from database
        """
        # MtM fields
        for fname, ftype in cls._mtm_get_fields():
            mtm_field_name = cls._mtm_field_name(fname)
            mtm_class = get_args(ftype)[0]
            # Get Generic type (List[<T>])
            if sys.version_info >= (3, 9):
                mtm_class = get_args(mtm_class)[0]

            mtm_data = data.pop(mtm_field_name, [])
            data[fname] = []

            for mtm_id in mtm_data:
                mtm_obj = await mtm_class.get(id=mtm_id)
                if mtm_obj is None:
                    raise ValueError(
                        f"The object with id '{mtm_id}' not found, "
                        f"field '{fname}'"
                    )
                data[fname].append(mtm_obj)

    @classmethod
    def _create_obj(cls, data: dict) -> "CollectionWorker":
        """
        Create object from database data
        """
        object_id = data.pop("_id", None)
        if object_id is None:
            raise ValueError("Arguments don't have _id")
        result = cls(**data)
        result._id = object_id
        return result

    @classmethod
    def _get_collection(cls) -> motor_asyncio.AsyncIOMotorCollection:
        """Return collection"""
        return (
            AMPODatabase()
            .get_db()
            .get_collection(
                cls.model_config[cfg_orm_collection],
                codec_options=cls.model_config.get(cfg_orm_bson_codec_options),
            )
        )

    @classmethod
    def _get_cfg_lock_record(cls) -> ORMLockRecord:
        """Get cfg lock record"""
        cfg_lock_record: Optional[dict] = cls.model_config.get(
            cfg_orm_lock_record
        )
        if cfg_lock_record is None:
            raise ValueError("Lock record is not enabled")
        return ORMLockRecord(**cfg_lock_record)

    @classmethod
    def _annotated_get_title(cls, ftype: Annotated) -> Optional[str]:
        if ftype.__metadata__ is None:
            return
        if len(ftype.__metadata__) == 0:
            return
        return ftype.__metadata__[0].title

    @staticmethod
    def _prepea_filter_get(filter: Optional[dict] = None) -> Optional[dict]:
        """
        Prepea filter data for methods 'find<*>'

        - Convert field 'id' to '_id'
        - Convert type of field '_id' str to ObjectId
        """
        if filter is None:
            return

        result = copy.deepcopy(filter)

        # Check id
        if "id" in result:
            result["_id"] = result.pop("id")
        if "_id" in result:
            if isinstance(result["_id"], str):
                result["_id"] = ObjectId(result["_id"])
        return result


async def init_collection():
    """
    Initialize all collection
    - Create indexies
    """
    for cls in CollectionWorker.__subclasses__():
        collection = cls._get_collection()

        # Indexes process
        for index_raw in cls.model_config.get(cfg_orm_indexes, []):
            orm_index = ORMIndex.model_validate(index_raw)

            # Generation name
            index_id = 1
            sorted(orm_index.keys)
            index_name = "_".join(orm_index.keys) + f"_{index_id}"

            # Check skip
            if orm_index.skip_initialization:
                continue

            # Create options
            index_is_ttl = False
            options = {}
            if orm_index.options is not None:
                options = orm_index.options.model_dump(exclude_none=True)
                index_is_ttl = orm_index.options.expireAfterSeconds is not None

            # Process TTL index
            if index_is_ttl:
                # condition
                if len(orm_index.keys) != 1:
                    raise ValueError("For TTL index, the key is set only one")
                # Check exist
                async for index in collection.list_indexes():
                    if index["key"] != bson.son.SON([(orm_index.keys[0], 1)]):
                        continue
                    if index.get("expireAfterSeconds") is None:
                        logger.warning(
                            "This index has no option expireAfterSeconds"
                        )
                        break
                    if (
                        index.get("expireAfterSeconds")
                        != orm_index.options.expireAfterSeconds
                    ):  # noqa: E501
                        await collection.drop_index(index_name)
                        logger.debug("The index '%s' was dropped", index_name)

            # Skip if for ttl not set expire time
            if index_is_ttl and orm_index.options.expireAfterSeconds == -1:
                continue

            # Create index
            cr_ind_opt: dict = {}
            if orm_index.commit_quorum_value is not None:
                cr_ind_opt["commitQuorum"] = orm_index.commit_quorum_value
            await period_check_future(
                aws=collection.create_indexes(
                    [
                        IndexModel(
                            keys=orm_index.keys,
                            name=index_name,
                            **options,
                        )
                    ],
                    **cr_ind_opt,
                ),
                period=40.0,
                msg=f"The index '{index_name}' is creating...",
                logger=logger,
            )
