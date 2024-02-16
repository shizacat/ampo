import logging
from typing import Optional, TypeVar, Type, List

from bson import ObjectId
from motor import motor_asyncio
from pydantic import BaseModel
from pymongo.errors import OperationFailure

from .db import AMPODatabase
from .utils import (
    ORMIndex, cfg_orm_collection, cfg_orm_indexes, cfg_orm_bson_codec_options
)

logger = logging.getLogger(__name__)


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


async def init_collection(custom_expiration: int = None):
    """Initialize all collection
    - Create indexies

    Args:
        custom_expiration (int, optional): Custom expiration
          for update indexes TLL in models (in sec.)
    """
    for cls in CollectionWorker.__subclasses__():
        collection = cls._get_collection()

        # Indexes process
        for field in cls.model_config.get(cfg_orm_indexes, []):
            orm_index = ORMIndex.model_validate(field)

            # Generation name
            index_name = _generate_index_name(orm_index.keys)

            # options
            options = _get_index_option(orm_index, custom_expiration)

            await _create_index(
                collection,
                orm_index.keys,
                index_name,
                options
            )


def _get_index_option(
        orm_index: ORMIndex,
        custom_expiration: int = None) -> dict:
    """ Return dict with options for indexes.

    Args:
        orm_index (ORMIndex): Object ORMIndex
        custom_expiration (int, optional): Custom expiration
          for update indexes TLL in models (in sec.)
    """
    options = {}
    if orm_index.options is not None:
        options = orm_index.options.model_dump(exclude_none=True)

        if options.get("expireAfterSeconds"):
            if custom_expiration:
                options.update({"expireAfterSeconds": custom_expiration})
    return options


def _generate_index_name(
        index_keys: List[str],
) -> str:
    """Generate name for index

    Args:
        index_keys (List[str]): ORMConfig model index keys
    """
    index_id = 1
    sorted(index_keys)
    return "_".join(index_keys) + f"_{index_id}"


async def _create_index(
        collection: motor_asyncio.AsyncIOMotorCollection,
        index_keys: List[str],
        index_name: str,
        options: dict
) -> None:
    """Creating a Collection Index

    Args:
        collection (motor_asyncio.AsyncIOMotorCollection): Collection object
        index_keys (List[str]): ORMConfig model index keys
        index_name (str): name new index
        options (dict): options index
    """
    is_created = False
    while is_created is False:
        try:
            await collection.create_index(
                index_keys,
                name=index_name,
                **options
            )
            is_created = True
            logger.debug("Index created")
        except OperationFailure:
            logger.debug("Index alreadey exist")
            await collection.drop_index(index_name)
