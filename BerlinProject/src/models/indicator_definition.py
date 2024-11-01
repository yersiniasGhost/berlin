from typing import Literal, Optional
from config.types import CANDLE_STICK_PATTERN, INDICATOR_TYPE, PyObjectId
from pydantic import BaseModel, Field as PydanticField


class IndicatorDefinition(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    name: str
    type: Literal[CANDLE_STICK_PATTERN, INDICATOR_TYPE]
    function: Optional[str] = None
    parameters: Optional[dict] = None
    ranges: Optional[dict] = None
    description: str = "NA"

