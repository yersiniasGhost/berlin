from typing import Dict, Optional
from config.pyobject_id import PyObjectId
from pydantic import BaseModel, Field as PydanticField

# test

class Monitor(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    user_id: PyObjectId = PydanticField(None)
    name: str
    description: str = "NA"
    threshold: float
    bear_threshold: float
    # target_reward: Optional[float] = 10.0
    # stop_loss: Optional[float] = 1.0
    # triggers are Custom IndicatorDefintion IDs (later, for now we are using the names)
    triggers: Dict[str, float]
    bear_triggers: Optional[Dict[str, float]] = None
    candles: Optional[Dict[str, float]] = None



