from bson.objectid import ObjectId
import json


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validateold(cls, v):
        if not isinstance(v, ObjectId):
            raise TypeError('ObjectId required')
        return v

    @classmethod
    def validate(cls, v, field=None, config=None):
        if isinstance(v, ObjectId):
            return v
        elif isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        else:
            raise ValueError("Invalid ObjectId")

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

    @classmethod
    def __get_pydantic_json_schema__(cls, **kwargs):
        return {"type": "string"}

# Define a custom JSON encoder
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, PyObjectId):
            return str(obj)
        return super().default(obj)

