from typing import Dict, List, Optional

from config.pyobject_id import PyObjectId
from bson import ObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator


class Monitor(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    user_id: PyObjectId = PydanticField(None)
    name: str
    description: str = "NA"
    threshold: float
    # triggers are Custom IndicatorDefintion IDs (later, for now we are using the names)
    triggers: Dict[str, float]
    candles: Optional[Dict[str, float]] = None



