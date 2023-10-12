import logging
from typing import Optional

from motor import motor_asyncio
from pymongo.database import Database


logger = logging.getLogger(__name__)


class AMPODatabase:
    """
    Singleton.
    Class for work with montodb
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.debug('Creating the object')
            cls._instance = super(AMPODatabase, cls).__new__(cls)
            cls._instance.__init(*args, **kwargs)
        return cls._instance

    def __init(self, url: str):
        """
        Initialization

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

    @classmethod
    def get_db(cls) -> motor_asyncio.AsyncIOMotorDatabase:
        if cls._instance is None:
            raise RuntimeError("Database not initialize")
        return cls._instance._db

    @classmethod
    def clear(cls):
        cls._instance = None
