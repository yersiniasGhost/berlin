"""
Clean test with positive trade sizes (using TradeReason to distinguish buy/sell)
"""

import json
from datetime import datetime
import sys
import os

# Add the src directory to the path to find the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from portfolios.portfolio_tool import Portfolio, TradeReason
from portfolios.trade_executor_simple import TradeExecutorSimple


class MockTickData:
    def __init__(self, price):
        self.close = price
        self.timestamp = datetime.now()


class SimpleMonitorConfig:
    def __init__(self, json_data):
        monitor_data = json_data.get('monitor', {})
        self.threshold = monitor_data.get('threshold', 0.8)
        self.bear_threshold = monitor_data.get('bear_threshold', 0.8)
        self.bars = monitor_data.get('bars', {})
        self.name = monitor_data.get('name', 'Test Monitor')


def test_simple_buy():
    """Test basic buy functionality"""

    # Load your JSON file
    json_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    with open(json_file, 'r') as f:
        monitor_json = json.load(f)

    monitor_config = SimpleMonitorConfig(monitor_json)

    print(f"✅ Loaded monitor: {monitor_config.name}")
    print(f"📊 Bars: {list(monitor_config.bars.keys())}")

    # Create executor with 0.5% stop loss
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.5  # 0.5% stop loss
    )

    print(f"📊 Initial position: {executor.portfolio.position_size}")

    # Create a tick
    tick = MockTickData(150.0)

    # Create bar scores that trigger bull bars
    bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bull':
            bar_scores[bar_name] = monitor_config.threshold + 0.1  # Above threshold
        else:
            bar_scores[bar_name] = 0.1  # Below threshold

    print(f"📊 Bar scores: {bar_scores}")

    # Execute the decision
    executor.make_decision(tick, {}, bar_scores)

    # Check result
    print(f"📊 Final position: {executor.portfolio.position_size}")
    print(f"📊 Trade history: {len(executor.portfolio.trade_history)} trades")

    if executor.portfolio.position_size > 0:
        print("✅ SUCCESS: Buy was executed!")
        trade = executor.portfolio.trade_history[0]
        print(f"   Trade: {trade.size} shares @ ${trade.price} ({trade.reason.value})")
        print(f"   Stop loss set at: ${executor.trailing_stop_price:.2f}")
        expected_stop = 150.0 * (1 - 0.005)  # 0.5% below entry
        print(f"   Expected stop: ${expected_stop:.2f}")
    else:
        print("❌ FAILED: No buy executed")


def test_stop_loss_trigger():
    """Test that stop loss properly clears position"""

    # Load your JSON file
    json_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    with open(json_file, 'r') as f:
        monitor_json = json.load(f)

    monitor_config = SimpleMonitorConfig(monitor_json)

    print(f"\n{'='*50}")
    print("TESTING STOP LOSS TRIGGER")
    print(f"{'='*50}")

    # Create executor with 0.5% stop loss
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.005  # 0.5% stop loss
    )

    # Step 1: Buy at $150
    buy_tick = MockTickData(150.0)
    bull_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bull':
            bull_bar_scores[bar_name] = monitor_config.threshold + 0.1
        else:
            bull_bar_scores[bar_name] = 0.1

    executor.make_decision(buy_tick, {}, bull_bar_scores)
    print(f"📊 Step 1 - Bought at $150.00")
    print(f"   Position: {executor.portfolio.position_size} shares")
    print(f"   Stop: ${executor.trailing_stop_price:.2f}")
    print(f"   Trades: {len(executor.portfolio.trade_history)}")

    # Step 2: Trigger stop loss at $149.20 (below $149.25 stop)
    no_signals = {bar_name: 0.1 for bar_name in monitor_config.bars.keys()}

    stop_tick = MockTickData(149.20)
    executor.make_decision(stop_tick, {}, no_signals)

    print(f"📊 Step 2 - Price dropped to $149.20 (below stop of $149.25)")
    print(f"   Position: {executor.portfolio.position_size} shares")
    print(f"   Stop: ${executor.trailing_stop_price:.2f}")
    print(f"   Trades: {len(executor.portfolio.trade_history)}")

    # Show all trades
    print(f"\n📋 TRADE HISTORY:")
    for i, trade in enumerate(executor.portfolio.trade_history):
        print(f"   Trade {i+1}: {trade.size} shares @ ${trade.price:.2f} ({trade.reason.value})")

    # Check results
    print(f"\n📋 RESULTS:")
    position_cleared = executor.portfolio.position_size == 0
    has_two_trades = len(executor.portfolio.trade_history) == 2

    print(f"   Position cleared: {position_cleared} ✅" if position_cleared else f"   Position cleared: {position_cleared} ❌")
    print(f"   Has 2 trades: {has_two_trades} ✅" if has_two_trades else f"   Has 2 trades: {has_two_trades} ❌")

    if position_cleared and has_two_trades:
        buy_trade = executor.portfolio.trade_history[0]
        sell_trade = executor.portfolio.trade_history[1]
        loss = (sell_trade.price - buy_trade.price) * buy_trade.size
        print(f"   Loss: ${loss:.2f}")
        print("✅ SUCCESS: Stop loss working correctly!")
    else:
        print("❌ FAILED: Stop loss didn't work correctly")


def test_trailing_stop_updates():
    """Test that trailing stop updates correctly but doesn't trigger early"""

    # Load your JSON file
    json_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    with open(json_file, 'r') as f:
        monitor_json = json.load(f)

    monitor_config = SimpleMonitorConfig(monitor_json)

    print(f"\n{'='*50}")
    print("TESTING TRAILING STOP UPDATES")
    print(f"{'='*50}")

    # Create executor with 0.5% stop loss
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.005  # 0.5% stop loss
    )

    # Step 1: Buy at $150
    buy_tick = MockTickData(150.0)
    bull_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bull':
            bull_bar_scores[bar_name] = monitor_config.threshold + 0.1
        else:
            bull_bar_scores[bar_name] = 0.1

    executor.make_decision(buy_tick, {}, bull_bar_scores)
    initial_stop = executor.trailing_stop_price
    print(f"📊 Step 1 - Bought at $150.00, Stop: ${initial_stop:.2f}")

    # Step 2: Price moves to $155 (should update stop loss)
    no_signals = {bar_name: 0.1 for bar_name in monitor_config.bars.keys()}

    tick_155 = MockTickData(155.0)
    executor.make_decision(tick_155, {}, no_signals)
    stop_after_155 = executor.trailing_stop_price
    print(f"📊 Step 2 - Price $155.00, Stop: ${stop_after_155:.2f}")

    # Step 3: Price moves to $160 (should update stop again)
    tick_160 = MockTickData(160.0)
    executor.make_decision(tick_160, {}, no_signals)
    stop_after_160 = executor.trailing_stop_price
    print(f"📊 Step 3 - Price $160.00, Stop: ${stop_after_160:.2f}")

    # Step 4: Price drops to $159.5 (should NOT trigger stop, stop should NOT move down)
    tick_159_5 = MockTickData(159.5)
    executor.make_decision(tick_159_5, {}, no_signals)
    stop_after_159_5 = executor.trailing_stop_price
    position_after_159_5 = executor.portfolio.position_size
    print(f"📊 Step 4 - Price $159.50, Stop: ${stop_after_159_5:.2f}, Position: {position_after_159_5}")

    # Check results
    print(f"\n📋 RESULTS:")
    stop_increased = stop_after_155 > initial_stop and stop_after_160 > stop_after_155
    stop_stayed_high = stop_after_159_5 == stop_after_160
    position_maintained = position_after_159_5 > 0

    print(f"   Stop increased with price: {stop_increased} ✅" if stop_increased else f"   Stop increased with price: {stop_increased} ❌")
    print(f"   Stop didn't move down: {stop_stayed_high} ✅" if stop_stayed_high else f"   Stop didn't move down: {stop_stayed_high} ❌")
    print(f"   Position maintained: {position_maintained} ✅" if position_maintained else f"   Position maintained: {position_maintained} ❌")

    if stop_increased and stop_stayed_high and position_maintained:
        print("✅ SUCCESS: Trailing stop working correctly!")
    else:
        print("❌ FAILED: Trailing stop not working as expected")


def test_bear_signal_sell():
    """Test that bear signals trigger a sell"""

    # Load your JSON file
    json_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    with open(json_file, 'r') as f:
        monitor_json = json.load(f)

    monitor_config = SimpleMonitorConfig(monitor_json)

    print(f"\n{'='*50}")
    print("TESTING BEAR SIGNAL SELL")
    print(f"{'='*50}")
    print(f"📊 Bear threshold: {monitor_config.bear_threshold}")

    # Show what bars are available
    print(f"📊 Available bars:")
    bear_bars_found = []
    for bar_name, bar_config in monitor_config.bars.items():
        bar_type = bar_config.get('type', 'unknown')
        print(f"   {bar_name}: {bar_type}")
        if bar_type == 'bear':
            bear_bars_found.append(bar_name)

    if not bear_bars_found:
        print("❌ WARNING: No bear bars found in configuration!")
        return

    # Create executor with 0.5% stop loss
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.005  # 0.5% stop loss
    )

    # Step 1: Buy first
    buy_tick = MockTickData(150.0)
    bull_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bull':
            bull_bar_scores[bar_name] = monitor_config.threshold + 0.1
        else:
            bull_bar_scores[bar_name] = 0.1

    executor.make_decision(buy_tick, {}, bull_bar_scores)
    print(f"📊 Step 1 - Bought: Position = {executor.portfolio.position_size} shares")

    # Step 2: Price moves up, stop updates
    tick_155 = MockTickData(155.0)
    no_signals = {bar_name: 0.1 for bar_name in monitor_config.bars.keys()}
    executor.make_decision(tick_155, {}, no_signals)
    print(f"📊 Step 2 - Price up to $155: Stop = ${executor.trailing_stop_price:.2f}")

    # Step 3: Bear signal triggers
    sell_tick = MockTickData(157.0)
    bear_bar_scores = {}

    for bar_name, bar_config in monitor_config.bars.items():
        bar_type = bar_config.get('type', 'unknown')
        if bar_type == 'bear':
            bear_bar_scores[bar_name] = monitor_config.bear_threshold + 0.1  # Above bear threshold
            print(f"📊 Setting bear bar '{bar_name}' to {bear_bar_scores[bar_name]} (threshold: {monitor_config.bear_threshold})")
        else:
            bear_bar_scores[bar_name] = 0.1

    print(f"📊 Step 3 - Triggering bear signal")
    executor.make_decision(sell_tick, {}, bear_bar_scores)

    # Check results
    print(f"\n📋 RESULTS:")
    print(f"   Final position: {executor.portfolio.position_size} shares")
    print(f"   Total trades: {len(executor.portfolio.trade_history)}")
    print(f"   Trailing stop after sell: ${executor.trailing_stop_price:.2f}")

    # Show all trades
    print(f"\n📋 TRADE HISTORY:")
    for i, trade in enumerate(executor.portfolio.trade_history):
        print(f"   Trade {i+1}: {trade.size} shares @ ${trade.price:.2f} ({trade.reason.value})")

    position_cleared = executor.portfolio.position_size == 0
    has_two_trades = len(executor.portfolio.trade_history) == 2

    if position_cleared and has_two_trades:
        buy_trade = executor.portfolio.trade_history[0]
        sell_trade = executor.portfolio.trade_history[1]
        profit = (sell_trade.price - buy_trade.price) * buy_trade.size
        print(f"   Profit: ${profit:.2f}")
        print("✅ SUCCESS: Bear signal sell executed!")
    else:
        print("❌ FAILED: Bear signal sell not working")
        print(f"   Expected: Position=0, Trades=2")
        print(f"   Actual: Position={executor.portfolio.position_size}, Trades={len(executor.portfolio.trade_history)}")


if __name__ == '__main__':
    test_simple_buy()
    test_stop_loss_trigger()
    test_trailing_stop_updates()
    test_bear_signal_sell()