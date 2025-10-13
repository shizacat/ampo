from bson.objectid import ObjectId

from ampo import errors as ampo_errors


def test_base_exception():
    # Create without document id
    a = ampo_errors.AmpoException("test")
    assert a.__str__() == "test"

    # Create with only document id
    i = ObjectId()
    a = ampo_errors.AmpoException(document_id=i)
    assert a.doc_id == i

    # both
    a = ampo_errors.AmpoException(msg="test", document_id=i)
    assert a.__str__() == "test"
    assert a.doc_id == i


def test_AmpoDocumentIsLock():
    a = ampo_errors.AmpoDocumentIsLock()
    assert a.__str__() == "The document is locked"


def test_AmpoDocumentNotFound():
    a = ampo_errors.AmpoDocumentNotFound()
    assert a.__str__() == "The document not found"
