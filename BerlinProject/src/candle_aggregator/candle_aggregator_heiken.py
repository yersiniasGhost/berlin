from datetime import datetime
from candle_aggregator.candle_aggregator import CandleAggregator
from models.tick_data import TickData


class CAHeiken(CandleAggregator):
    """
    Heiken Ashi candle aggregator.
    Creates smoothed Heiken Ashi candles from tick data.
    """

    def _create_new_candle(self, tick_data: TickData, candle_start_time: datetime) -> TickData:
        """Create new Heiken Ashi candle from first tick"""
        ha_open = self._calculate_ha_open()
        ha_close = self._calculate_ha_close_from_tick(tick_data)

        # For very first candle, use tick close as open
        if not self.history:
            ha_open = tick_data.close

        return TickData(
            symbol=self.symbol,
            timestamp=candle_start_time,
            open=ha_open,
            high=ha_close,
            low=ha_close,
            close=ha_close,
            volume=tick_data.volume,
            time_increment=self.timeframe
        )

    def _update_existing_candle(self, tick_data: TickData) -> None:
        """Update current Heiken Ashi candle with new tick"""
        ha_close = self._calculate_ha_close_from_tick(tick_data)
        ha_high = self._calculate_ha_high(tick_data, ha_close)
        ha_low = self._calculate_ha_low(tick_data, ha_close)

        self._update_ha_values(ha_high, ha_low, ha_close)
        self._update_volume(tick_data.volume)

    def _calculate_ha_open(self) -> float:
        if not self.history:
            return 0.0

        prev_candle = self.history[-1]
        return (prev_candle.open + prev_candle.close) / 2

    def _calculate_ha_close_from_tick(self, tick_data: TickData) -> float:
        return (tick_data.open + tick_data.high + tick_data.low + tick_data.close) / 4

    def _calculate_ha_high(self, tick_data: TickData, ha_close: float) -> float:
        return max(
            tick_data.high,
            self.current_candle.open,
            ha_close
        )

    def _calculate_ha_low(self, tick_data: TickData, ha_close: float) -> float:
        return min(
            tick_data.low,
            self.current_candle.open,
            ha_close
        )

    def _update_ha_values(self, ha_high: float, ha_low: float, ha_close: float) -> None:
        self.current_candle.high = ha_high
        self.current_candle.low = ha_low
        self.current_candle.close = ha_close

    def _update_volume(self, volume: float) -> None:
        self.current_candle.volume += volume

    def _get_aggregator_type(self) -> str:
        return "heiken"
