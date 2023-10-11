from pydantic import ConfigDict


# Definition
cfg_orm_collection = "orm_collection"


class ORMConfig(ConfigDict):
    """
    Custon configuration for Collection
    """
    # Name of collection
    orm_collection: str
