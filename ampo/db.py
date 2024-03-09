from typing import Optional

from motor import motor_asyncio
from pymongo.database import Database


class SingletonMeta(type):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        cls._instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)

        return cls._instance

    def clear(cls):
        cls._instance = None


class AMPODatabase(metaclass=SingletonMeta):
    """
    Singleton.
    Class for work with mongodb
    """

    def __init__(self, url: str):
        """

        Parameters
        ----------
            url : str
                URL for connect to mongodb
        """
        self._client: Optional[motor_asyncio.AsyncIOMotorClient] = None
        self._db: Optional[Database] = None

        # Connect
        self._client = motor_asyncio.AsyncIOMotorClient(url)
        self._db = self._client.get_default_database()

    def get_db(self) -> motor_asyncio.AsyncIOMotorDatabase:
        return self._db
