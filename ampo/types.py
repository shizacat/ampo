import sys
from typing import Any, Callable

from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue
from pydantic import GetJsonSchemaHandler
from bson.objectid import ObjectId


if sys.version_info >= (3, 10):
    from typing import Annotated
else:
    from typing_extensions import Annotated


class _PydanticObjectIdAnnotation:
    """
    Based on
    https://docs.pydantic.dev/latest/concepts/types/#handling-third-party-types

    https://stackoverflow.com/questions/76686888/using-bson-objectid-in-pydantic-v2/76837550#76837550
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Callable[[Any], core_schema.CoreSchema],
    ) -> core_schema.CoreSchema:
        def validate_from_str(value: str) -> ObjectId:
            if not ObjectId.is_valid(value):
                raise ValueError("Invalid ObjectId string")
            return ObjectId(value)

        def validate_python_objectid(value: Any) -> ObjectId:
            if isinstance(value, ObjectId):
                return value
            raise ValueError("Expected ObjectId")

        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_plain_validator_function(
                validate_from_str),
            python_schema=core_schema.union_schema([
                # Alternative
                # core_schema.is_instance_schema(ObjectId),
                core_schema.no_info_plain_validator_function(
                    validate_python_objectid),
                core_schema.no_info_plain_validator_function(
                    validate_from_str),
            ]),
            serialization=core_schema.to_string_ser_schema(),
            # serialization=core_schema.plain_serializer_function_ser_schema(
            #     lambda v: str(v),
            #     return_schema=core_schema.str_schema()
            # )
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.str_schema())


PydanticObjectId = Annotated[ObjectId, _PydanticObjectIdAnnotation]
