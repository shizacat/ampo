

from pydantic import BaseModel
from bson.objectid import ObjectId

from ampo import PydanticObjectId


class A(BaseModel):
    """
    The model for testing
    """

    t: PydanticObjectId


def test_type():
    # Create from string
    a = A(t="6326015616823e8695183666")
    assert isinstance(a.t, ObjectId)

    # Create from ObjectId
    a = A(t=ObjectId("6326015616823e8695183666"))
    assert isinstance(a.t, ObjectId)

    # Serialize to json
    a = A(t=ObjectId("6326015616823e8695183666"))
    assert a.model_dump_json() == '{"t":"6326015616823e8695183666"}'

    # Serialize to dict
    a = A(t=ObjectId("6326015616823e8695183666"))
    assert a.model_dump() == {'t': ObjectId('6326015616823e8695183666')}
    assert a.model_dump(mode="json") == {"t": "6326015616823e8695183666"}

    # Create from json
    a = A.model_validate({'t': '6326015616823e8695183666'})
    assert isinstance(a.t, ObjectId)

    # Generate json schema
    a = A.model_json_schema()
    assert a == {
        "description": "The model for testing",
        "properties": {
            "t": {
                "title": "T",
                "type": 'string'
            }
        },
        "required": ["t"],
        "title": "A",
        "type": "object"
    }
