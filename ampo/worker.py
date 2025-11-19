import asyncio
import copy
import functools
import typing
from contextlib import asynccontextmanager
import datetime
from typing import (
    Optional,
    TypeVar,
    Type,
    List,
    Union,
    Tuple,
    AsyncIterator,
    AsyncGenerator,
    get_origin,
    get_args,
)
from typing_extensions import Annotated, TypeAliasType, Any
import sys

import bson.son
from bson import ObjectId
from motor import motor_asyncio
from pydantic import BaseModel, Field, RootModel, field_validator
from pymongo import IndexModel, ReturnDocument

from .db import AMPODatabase
from .utils import (
    ORMIndex,
    ORMLockRecord,
    ORMHooks,
    cfg_orm_collection,
    cfg_orm_indexes,
    cfg_orm_bson_codec_options,
    cfg_orm_lock_record,
    cfg_orm_hooks,
    datetime_utcnow_tz,
    period_check_future,
)
from .log import logger
from . import errors as ampo_errors


T = TypeVar("T", bound="CollectionWorker")


# For Python 3.9+ uses TypeAlias
if sys.version_info >= (3, 9):
    RFManyToMany = Annotated[
        List[T], Field(default_factory=list, title="RFManyToMany")
    ]
    RFOneToMany = Annotated[Optional[T], Field(None, title="RFOneToMany")]
else:
    RFManyToMany = TypeAliasType(
        "RFManyToMany",
        Annotated[List[T], Field(default_factory=list)],
        # type_params=(T,),
    )
    RFOneToMany = TypeAliasType(
        "RFOneToMany",
        Annotated[Optional[T], Field(None, title="RFOneToMany")],
        # type_params=(T,),
    )


# class CollectionBulk(RootModel):
#     """
#     Base class for bulk operations
#     """
#     root = list["CollectionWorker"]

#     @field_validator("root")
#     @classmethod
#     def validate_all_item(cls, v: List[Any]) -> List["CollectionWorker"]:
#         if not all(isinstance(item, CollectionWorker) for item in v):
#             raise ValueError("All items must be CollectionWorker instances")
#         return v


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

    async def save(self, context: Optional[dict] = None):
        """
        Save object to db.
        If the object exists into db, then the object will be replace.
        This is will checked by '_id' field.
        """
        collection = self._get_collection()

        async with self._save_process(context) as model_dump:
            if self._id is None:
                # insert
                result = await collection.insert_one(model_dump)
                self._id = result.inserted_id
            else:
                # update
                await collection.replace_one({"_id": self._id}, model_dump)
                # TODO: Not shure what better
                # await collection.update_one(
                #     {"_id": self._id}, {"$set": model_dump}, upsert=False)

    @classmethod
    async def save_bulk(
        self,
        items: list[T],
        contexts: Optional[list[dict]] = None
    ):
        """
        Save many objects
        TODO: Add annottaion on General

        Return

        """
        collection = self._get_collection()

        # assert
        if not all(isinstance(item, CollectionWorker) for item in items):
            raise ValueError("All items must be CollectionWorker instances")
        if contexts is not None and len(items) != len(contexts):
            raise ValueError("The length items and contexts don't equal")

        # split insert/update
        linsert: list[tuple] = []
        lupdate: list = []
        for idx, item in enumerate(items):
            if item._id is None:
                context = None if contexts is None else contexts[idx]
                linsert.append((item, item._save_process(context)))
            else:
                lupdate.append(item)

        # insert many
        if linsert:
            result = await collection.insert_many([
                await cmanager.__aenter__() for item, cmanager in linsert
            ])
            for idx, inserted_id in enumerate(result.inserted_ids):
                linsert[idx][0]._id = inserted_id

            # run post hook for insert
            for item, cmanager in linsert:
                await cmanager.__aexit__(None, None, None)

        # update many
        for item in lupdate:
            await item.save()

    @classmethod
    async def get(
        cls: Type[T],
        filter: Optional[dict] = None,
        skip_not_found: bool = False,
        **kwargs
    ) -> Optional[T]:
        """
        Get one object from database
        """
        collection = cls._get_collection()

        data = await collection.find_one(
            filter=CollectionWorker._prepea_filter_get(filter),
            **kwargs
        )
        if data is None:
            return
        await cls._rel_get_data(data=data, skip_not_found=skip_not_found)
        return cls._create_obj(data)

    @classmethod
    async def get_all(
        cls: Type[T],
        filter: Optional[dict] = None,
        skip_not_found: bool = False,
        **kwargs
    ) -> List[T]:
        """
        Search all object by filter.

        Parameters analogous from the library pymongo:
        https://pymongo.readthedocs.io/en/4.9/api/pymongo/collection.html#pymongo.collection.Collection.find

        Args:
            filter (dict): filter for search
            skip_not_found (bool): If True, then the relation object
                will be skipped if the object is not found
        """
        result = []

        collection = cls._get_collection()

        data = await collection.find(
            filter=CollectionWorker._prepea_filter_get(filter), **kwargs
        ).to_list(None)
        for d in data:
            await cls._rel_get_data(data=d, skip_not_found=skip_not_found)
            result.append(cls._create_obj(d))
        return result

    async def delete(self, context: Optional[dict] = None):
        """
        Delete object from database
        """
        collection = self._get_collection()

        await self._run_hooks("pre_delete", context)

        if self._id is None:
            raise ValueError("Object not created")
        await collection.delete_one({"_id": self._id})

        await self._run_hooks("post_delete", context)

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
    async def get_and_lock(
        cls: Type[T],
        filter: Optional[dict] = None,
        skip_not_found: bool = False,
    ) -> Optional[T]:
        """Get and lock the record

        Raises:
            AmpoDocumentIsLock - if the record is locked

        Return
            The record, locked.
            None if record not exists
        """
        l_dt_start = datetime_utcnow_tz()
        lock_is_expired: bool = False
        part_update = {
            "$set": {
                cls._get_cfg_lock_record().lock_field: True,
                cls._get_cfg_lock_record().lock_field_time_start: l_dt_start,
            }
        }

        # Create filter
        filter_p = CollectionWorker._prepea_filter_get(filter)

        # Try to find, receive and lock the record
        filter_tmp = copy.deepcopy(filter_p)
        filter_tmp.update({cls._get_cfg_lock_record().lock_field: False})
        data: Optional[dict] = await cls._get_collection().find_one_and_update(
            filter=filter_tmp,
            update=part_update,
            return_document=ReturnDocument.AFTER
        )

        # Try to find the locked record
        if data is None and cls._get_cfg_lock_record().allow_find_locked:
            filter_tmp = copy.deepcopy(filter_p)
            filter_tmp.update(
                {
                    cls._get_cfg_lock_record().lock_field: True,
                    cls._get_cfg_lock_record().lock_field_time_start: {
                        "$lt": l_dt_start
                        - datetime.timedelta(
                            seconds=cls._get_cfg_lock_record().lock_max_period_sec  # noqa: E501
                        )
                    },
                }
            )
            data = await cls._get_collection().find_one_and_update(
                filter=filter_tmp,
                update=part_update,
                return_document=ReturnDocument.AFTER  # BEFORE
            )
            lock_is_expired = True

        # Check, the record exists
        if data is None:
            if (await cls.exists(**filter)):
                raise ampo_errors.AmpoDocumentIsLock()
            # The object not found
            return None

        # Create object
        await cls._rel_get_data(data=data, skip_not_found=skip_not_found)
        obj = cls._create_obj(data)
        if lock_is_expired:
            logger.warning(f"Lock is expired. ObjectID: {obj.id}.")
        return obj

    async def reset_lock(self):
        """Reset lock

        Raises:
            ValueError - if the object don't saved
        """
        # check object is saved
        if self._id is None:
            raise ValueError("Not saved")

        # update lock field
        self.lock_field = False

        # update document
        await self._get_collection().update_one(
            filter=CollectionWorker._prepea_filter_get({"_id": self._id}),
            update={
                "$set": {
                    self._get_cfg_lock_record().lock_field: self.lock_field
                }
            },
        )

    @classmethod
    @asynccontextmanager
    async def get_and_lock_context(
        cls: Type[T], **kwargs: dict
    ) -> AsyncIterator[T]:
        """Get and lock context

        Raises:
            AmpoDocumentIsLock - if the record is locked
        """
        obj = await cls.get_and_lock(filter=kwargs)
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
            asyncio.TimeoutError
            AmpoDocumentNotFound
        """
        loop = asyncio.get_running_loop()
        obj: Optional[T] = None

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

            try:
                obj = await cls.get_and_lock(filter=filter)
                if obj is None:
                    raise ampo_errors.AmpoDocumentNotFound(
                        "The object not found")
                # The object is got and locked
                yield obj
            except ampo_errors.AmpoDocumentIsLock:
                continue
            finally:
                if obj is not None:
                    await obj.reset_lock()
            break

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

        # Relations exclude
        kwargs["exclude"].extend([x for x, _ in self._mtm_get_fields()])
        kwargs["exclude"].extend([x for x, _ in self._otm_get_fields()])

        # Dump
        data = super().model_dump(*args, **kwargs)

        # MtM add fields
        for fname, ftype in self._mtm_get_fields():
            mtm_field_name = self._mtm_field_name(fname)
            # Set default value
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

        # OtM add fields
        for fname, ftype in self._otm_get_fields():
            otm_field_name = self._otm_field_name(fname)
            # Set default value
            data[otm_field_name] = None
            #
            otm_obj = getattr(self, fname)

            # Handling None for OtM objects
            if otm_obj is not None:
                assert isinstance(otm_obj, CollectionWorker)
                if not skip_save_check and otm_obj.id is None:
                    raise ValueError(
                        f"The object in the field '{fname}' is not saved"
                    )
                data[otm_field_name] = otm_obj._id

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

    @property
    def lock_field(self) -> bool:
        """
        Return value of lock field state
        """
        return getattr(self, self._get_cfg_lock_record().lock_field)

    @lock_field.setter
    def lock_field(self, value: bool):
        """
        Setter for lock field state
        """
        if not isinstance(value, bool):
            raise TypeError("Got not bool")
        setattr(self, self._get_cfg_lock_record().lock_field, value)

    @property
    def lock_field_time_start(self) -> datetime.datetime:
        """
        Return value of lock field time start
        """
        cfg_lock_record = self._get_cfg_lock_record()
        return getattr(self, cfg_lock_record.lock_field_time_start)

    @lock_field_time_start.setter
    def lock_field_time_start(self, value: datetime.datetime):
        if not isinstance(value, datetime.datetime):
            raise TypeError("Got not datetime")
        setattr(self, self._get_cfg_lock_record().lock_field_time_start, value)

    # ___ Private methods ___

    async def _run_hooks(self, hook_name: str, context: Optional[dict] = None):
        """
        Run all hooks by name
        """
        try:
            hooks = getattr(self._get_hooks(), hook_name)
        except AttributeError:
            raise RuntimeError(f"The attribute {hook_name} not found")

        for hook in hooks:
            await hook(self, context)

    @asynccontextmanager
    async def _save_process(
        self, context: Optional[dict] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Handling save objects, it will not touch the database

        Return
            model dump for insert to db
        """
        await self._run_hooks("pre_save", context)
        yield self.model_dump()
        await self._run_hooks("post_save", context)

    @classmethod
    def _rel_get_fields(
        cls, cmp_type: Union[RFManyToMany, RFOneToMany]
    ) -> List[Tuple[str, str]]:
        """
        Return list of fields for relations fields

        For Python 3.12+ ftype is:
            typing.Annotated[typing.List[<T>]
        """
        result = []

        for fname, ftype in cls.__annotations__.items():
            if sys.version_info >= (3, 9):
                title_name: str = cmp_type.__metadata__[0].title
                if (
                    get_origin(ftype) == typing.Annotated
                    and cls._annotated_get_title(ftype) == title_name
                ):
                    result.append((fname, ftype))
            else:
                if get_origin(ftype) == cmp_type:
                    result.append((fname, ftype))
        return result

    @classmethod
    def _otm_get_fields(cls) -> List[Tuple[str, str]]:
        """
        Return list of fields for one-to-many relations
        """
        return cls._rel_get_fields(RFOneToMany)

    @classmethod
    def _mtm_get_fields(cls) -> List[Tuple[str, str]]:
        """
        Return list of fields for many-to-many relations
        """
        return cls._rel_get_fields(RFManyToMany)

    @classmethod
    def _mtm_field_name(cls, filed_name: str) -> str:
        """
        Generate name of field for many-to-many relations
        which will be used for save in database
        """
        mtm_suffix = "_ids"
        return f"{filed_name}{mtm_suffix}"

    @classmethod
    def _otm_field_name(cls, filed_name: str) -> str:
        """
        Generate name of field for one-to-many relations
        which will be used for save in database
        """
        otm_suffix = "_id"
        return f"{filed_name}{otm_suffix}"

    @classmethod
    async def _rel_get_data(cls, data: dict, skip_not_found: bool = False):
        """
        Added to the data relation fields (mtm)

        Args:
            data - dict with data of parent, from database
            skip_not_found - if True, then do not raise an exception
                if the relation object is not found.
                This object will be exclude.
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
                mtm_obj = await mtm_class.get(filter={"id": mtm_id})
                if mtm_obj is None:
                    msg = (
                        f"The object with id '{mtm_id}' not found, "
                        f"field '{fname}'"
                    )
                    if skip_not_found:
                        logger.warning(msg)
                        continue
                    else:
                        raise ValueError(msg)
                data[fname].append(mtm_obj)

        # OtM fields
        for fname, ftype in cls._otm_get_fields():
            otm_field_name = cls._otm_field_name(fname)
            otm_class = get_args(ftype)[0]
            # Get Generic type (List[<T>])
            if sys.version_info >= (3, 9):
                otm_class = get_args(otm_class)[0]
            otm_id = data.pop(otm_field_name, None)
            otm_obj = None
            if otm_id is not None:
                otm_obj = await otm_class.get(filter={"id": otm_id})
                if otm_obj is None:
                    msg = (
                        f"The object with id '{otm_id}' not found, "
                        f"field '{fname}'"
                    )
                    if skip_not_found:
                        logger.warning(msg)
                        otm_obj = None
                    else:
                        raise ValueError(msg)
            data[fname] = otm_obj

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
    @functools.lru_cache(maxsize=None)
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

    @classmethod
    def _get_hooks(cls) -> ORMHooks:
        """
        Return hooks list
        """
        hooks: dict = cls.model_config.get(cfg_orm_hooks)
        if hooks is None:
            return ORMHooks()
        return ORMHooks(**hooks)

    @classmethod
    def _subclasses_all(cls) -> List["CollectionWorker"]:
        """
        Returns all subclasses including descendant subclasses
        """
        result = []
        for subclass in cls.__subclasses__():
            if subclass.model_config.get(cfg_orm_collection):
                result.append(subclass)
            result.extend(subclass._subclasses_all())
        return result

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
    for cls in CollectionWorker._subclasses_all():
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
