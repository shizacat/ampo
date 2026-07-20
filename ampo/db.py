from typing import Optional

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase


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
        self._client: Optional[AsyncMongoClient] = None
        self._db: Optional[AsyncDatabase] = None

        # Connect
        self._client = AsyncMongoClient(url)
        self._db = self._client.get_default_database()

    def get_db(self) -> AsyncDatabase:
        return self._db

    async def close(self):
        """Close the AsyncMongoClient connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._db = None

    @classmethod
    async def aclose(cls):
        """Close the client (if any) and clear the singleton."""
        if cls._instance is not None:
            await cls._instance.close()
        cls.clear()
