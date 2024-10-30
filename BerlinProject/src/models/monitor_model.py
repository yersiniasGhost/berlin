from typing import Dict, Optional
from config.pyobject_id import PyObjectId
from pydantic import BaseModel, Field as PydanticField


class Monitor(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    user_id: PyObjectId = PydanticField(None)
    name: str
    description: str = "NA"
    threshold: float
    # triggers are Custom IndicatorDefintion IDs (later, for now we are using the names)
    triggers: Dict[str, float]
    candles: Optional[Dict[str, float]] = None



