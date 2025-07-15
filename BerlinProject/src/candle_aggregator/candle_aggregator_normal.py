# data_streamer/ca_normal.py
from datetime import datetime
from candle_aggregator.candle_aggregator import CandleAggregator
from models.tick_data import TickData


class CANormal(CandleAggregator):
    """
    Normal OHLC candle aggregator.
    Creates standard candlesticks from tick data.
    """

    def _create_new_candle(self, tick_data: TickData, candle_start_time: datetime) -> TickData:
        """Create new normal OHLC candle from first tick"""
        return TickData(
            symbol=self.symbol,
            timestamp=candle_start_time,
            open=tick_data.close,
            high=tick_data.close,
            low=tick_data.close,
            close=tick_data.close,
            volume=tick_data.volume,
            time_increment=self.timeframe
        )

    def _update_existing_candle(self, tick_data: TickData) -> None:
        self._update_high(max(tick_data.open, tick_data.high, tick_data.low, tick_data.close))
        self._update_low(min(tick_data.open, tick_data.high, tick_data.low, tick_data.close))
        self._update_close(tick_data.close)
        self._update_volume(tick_data.volume)

    def _update_high(self, price: float) -> None:
        """Update candle high with new price"""
        self.current_candle.high = max(self.current_candle.high, price)

    def _update_low(self, price: float) -> None:
        """Update candle low with new price"""
        self.current_candle.low = min(self.current_candle.low, price)

    def _update_close(self, price: float) -> None:
        """Update candle close with latest price"""
        self.current_candle.close = price

    def _update_volume(self, volume: float) -> None:
        """Add volume to current candle"""
        self.current_candle.volume += volume

    def _get_aggregator_type(self) -> str:
        """Return aggregator type identifier"""
        return "normal"
