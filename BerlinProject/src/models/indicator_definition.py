from typing import Literal, Optional
from config.types import CANDLE_STICK_PATTERN, INDICATOR_TYPE, PyObjectId
from pydantic import BaseModel, Field as PydanticField


#  Current args for app config are 1m, 5m, 15m, 30m ,1h. Then "normal" or "heiken"

class IndicatorDefinition(BaseModel):
    id: Optional[PyObjectId] = PydanticField(None, alias="_id")
    name: str
    type: Literal[CANDLE_STICK_PATTERN, INDICATOR_TYPE]
    indicator_class: str
    parameters: Optional[dict] = PydanticField(default=None)
    ranges: Optional[dict] = PydanticField(default=None)
    description: str = PydanticField(default="NA")
    agg_config: Optional[str] = PydanticField(default=None)
    calc_on_pip: bool = PydanticField(default=False)

    #     change time increment to agg_config which is mix of interval and HA or normal

    def get_timeframe(self) -> str:
        """Extract timeframe from agg_config"""
        if not self.agg_config:
            return "1m"
        return self.agg_config.split('-')[0]

    def get_aggregator_type(self) -> str:
        """Extract aggregator type from agg_config"""
        if not self.agg_config:
            return "normal"
        parts = self.agg_config.split('-')
        return parts[1].lower() if len(parts) > 1 else "normal"
