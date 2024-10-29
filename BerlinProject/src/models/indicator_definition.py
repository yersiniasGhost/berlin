from typing import Literal
from config.types import CANDLE_STICK_PATTERN, INDICATOR_TYPE, PyObjectId
from pydantic import BaseModel, Field as PydanticField


class IndicatorDefinition(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    name: str
    function: str
    type: Literal[CANDLE_STICK_PATTERN, INDICATOR_TYPE]
    parameters: dict
    description: str = "NA"
