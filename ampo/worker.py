from typing import Optional, TypeVar, Type, List

import bson.son
from bson import ObjectId
from motor import motor_asyncio
from pydantic import BaseModel

from .db import AMPODatabase
from .utils import (
    ORMIndex, cfg_orm_collection, cfg_orm_indexes, cfg_orm_bson_codec_options
)
from .log import logger


T = TypeVar('T')


class CollectionWorker(BaseModel):
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
        kwargs = CollectionWorker._prepea_filter_get(**kwargs)

        # get
        data = await collection.find_one(kwargs)
        if data is None:
            return
        return cls._create_obj(**data)

    @classmethod
    async def get_all(cls: Type[T], **kwargs) -> List[T]:
        """
        Search all object by filter
        """
        collection = cls._get_collection()
        kwargs = CollectionWorker._prepea_filter_get(**kwargs)

        data = await collection.find(kwargs).to_list(None)
        return [cls._create_obj(**d) for d in data]

    @classmethod
    def update_expiration_value(
        cls: Type[T], field: str, expire_seconds: int
    ):
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
    def _create_obj(cls, **kwargs):
        """
        Create object from database data
        """
        object_id = kwargs.pop("_id", None)
        if object_id is None:
            raise ValueError("Arguments don't have _id")
        result = cls(**kwargs)
        result._id = object_id
        return result

    @classmethod
    def _get_collection(cls) -> motor_asyncio.AsyncIOMotorCollection:
        """ Return collection """
        return AMPODatabase.get_db().get_collection(
            cls.model_config[cfg_orm_collection],
            codec_options=cls.model_config.get(cfg_orm_bson_codec_options)
        )

    @staticmethod
    def _prepea_filter_get(**kwargs) -> dict:
        """
        Prepea filter data for methods 'get'
        """
        # check id
        if "id" in kwargs:
            kwargs["_id"] = kwargs.pop("id")
        if "_id" in kwargs:
            if isinstance(kwargs["_id"], str):
                kwargs["_id"] = ObjectId(kwargs["_id"])
        return kwargs


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
                            "This index has no option expireAfterSeconds")
                        break
                    if index.get("expireAfterSeconds") != orm_index.options.expireAfterSeconds:  # noqa: E501
                        await collection.drop_index(index_name)
                        logger.debug("The index '%s' was dropped", index_name)

            # Skip if for ttl not set expire time
            if index_is_ttl and orm_index.options.expireAfterSeconds == -1:
                continue

            await collection.create_index(
                orm_index.keys,
                name=index_name,
                **options
            )
