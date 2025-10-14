from __future__ import annotations

from bson.objectid import ObjectId


class AmpoException(Exception):
    """The base exception for AMPO"""

    def __init__(
        self, msg: None | str = None, document_id: None | ObjectId = None
    ):
        super().__init__(msg)
        self._document_id = document_id

    @property
    def doc_id(self) -> None | ObjectId:
        return self._document_id


class AmpoDocumentNotFound(AmpoException):

    def __init__(self, msg: None | str = None, **kwargs):
        if msg is None:
            msg = "The document not found"
        super().__init__(msg=msg, **kwargs)


class AmpoDocumentIsLock(AmpoException):

    def __init__(self, msg: None | str = None, **kwargs):
        if msg is None:
            msg = "The document is locked"
        super().__init__(msg=msg, **kwargs)
