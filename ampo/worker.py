from typing import Optional, TypeVar, Type

from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
from motor import motor_asyncio

from .db import AMPODatabase
from .utils import ORMConfig, cfg_orm_collection


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
    async def get_all(cls: Type[T], **kwargs) -> Optional[T]:
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
        """
        Return collection
        """
        db = AMPODatabase.get_db()
        return db[cls.model_config[cfg_orm_collection]]

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
