"""
Super simple unit test
"""

import json
from datetime import datetime


import sys
import os
sys.path.append(os.path.dirname(__file__))

from .portfolio_tool import Portfolio, TradeReason
from .trade_executor_simple import TradeExecutorSimple


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
    """One simple test - trigger a buy"""

    # Load your JSON file
    json_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    with open(json_file, 'r') as f:
        monitor_json = json.load(f)

    monitor_config = SimpleMonitorConfig(monitor_json)

    print(f"✅ Loaded monitor: {monitor_config.name}")
    print(f"📊 Bars: {list(monitor_config.bars.keys())}")

    # Create executor (which owns the portfolio)
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.5
    )

    # Get the portfolio from the executor
    portfolio = executor.get_portfolio()

    print(f"📊 Initial position: {portfolio.position_size}")

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

    # Process indicators (no portfolio parameter needed now)
    executor.process_indicators(tick, {}, bar_scores)

    # Check result
    print(f"📊 Final position: {portfolio.position_size}")
    print(f"📊 Trade history: {len(portfolio.trade_history)} trades")

    if portfolio.position_size > 0:
        print("✅ SUCCESS: Buy was executed!")
        trade = portfolio.trade_history[0]
        print(f"   Trade: {trade.size} @ ${trade.price} ({trade.reason.value})")
        print(f"   Stop loss set at: ${executor.trailing_stop_price:.2f}")
    else:
        print("❌ FAILED: No buy executed")


def test_trailing_stop_updates():
    """Test that trailing stop loss updates as price moves up"""

    # Load your JSON file
    json_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    with open(json_file, 'r') as f:
        monitor_json = json.load(f)

    monitor_config = SimpleMonitorConfig(monitor_json)

    print(f"\n{'='*50}")
    print("TESTING TRAILING STOP UPDATES")
    print(f"{'='*50}")

    # Create executor
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.5
    )

    portfolio = executor.get_portfolio()

    # Step 1: Buy at $150
    buy_tick = MockTickData(150.0)
    bull_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bull':
            bull_bar_scores[bar_name] = monitor_config.threshold + 0.1
        else:
            bull_bar_scores[bar_name] = 0.1

    executor.process_indicators(buy_tick, {}, bull_bar_scores)
    initial_stop = executor.trailing_stop_price
    print(f"📊 Step 1 - Bought at $150.00, Stop: ${initial_stop:.2f}")

    # Step 2: Price moves to $155 (should update stop loss)
    no_signals = {bar_name: 0.1 for bar_name in monitor_config.bars.keys()}

    tick_155 = MockTickData(155.0)
    executor.process_indicators(tick_155, {}, no_signals)
    stop_after_155 = executor.trailing_stop_price
    print(f"📊 Step 2 - Price $155.00, Stop: ${stop_after_155:.2f}")

    # Step 3: Price moves to $160 (should update stop again)
    tick_160 = MockTickData(160.0)
    executor.process_indicators(tick_160, {}, no_signals)
    stop_after_160 = executor.trailing_stop_price
    print(f"📊 Step 3 - Price $160.00, Stop: ${stop_after_160:.2f}")

    # Step 4: Price drops to $158 (stop should NOT move down)
    tick_158 = MockTickData(158.0)
    executor.process_indicators(tick_158, {}, no_signals)
    stop_after_158 = executor.trailing_stop_price
    print(f"📊 Step 4 - Price $158.00, Stop: ${stop_after_158:.2f}")

    # Check results
    print(f"\n📋 RESULTS:")
    print(f"   Initial stop ($150 entry): ${initial_stop:.2f}")
    print(f"   After $155: ${stop_after_155:.2f} {'✅' if stop_after_155 > initial_stop else '❌'}")
    print(f"   After $160: ${stop_after_160:.2f} {'✅' if stop_after_160 > stop_after_155 else '❌'}")
    print(f"   After $158: ${stop_after_158:.2f} {'✅' if stop_after_158 == stop_after_160 else '❌'}")

    if (stop_after_155 > initial_stop and
        stop_after_160 > stop_after_155 and
        stop_after_158 == stop_after_160):
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

    # Create executor
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.5
    )

    portfolio = executor.get_portfolio()

    # Step 1: Buy first
    buy_tick = MockTickData(150.0)
    bull_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bull':
            bull_bar_scores[bar_name] = monitor_config.threshold + 0.1
        else:
            bull_bar_scores[bar_name] = 0.1

    executor.process_indicators(buy_tick, {}, bull_bar_scores)
    print(f"📊 Step 1 - Bought: Position = {portfolio.position_size}")

    # Step 2: Price moves up, stop updates
    tick_155 = MockTickData(155.0)
    no_signals = {bar_name: 0.1 for bar_name in monitor_config.bars.keys()}
    executor.process_indicators(tick_155, {}, no_signals)
    print(f"📊 Step 2 - Price up to $155: Stop = ${executor.trailing_stop_price:.2f}")

    # Step 3: Bear signal triggers
    sell_tick = MockTickData(157.0)
    bear_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bear':
            bear_bar_scores[bar_name] = monitor_config.bear_threshold + 0.1  # Above bear threshold
        else:
            bear_bar_scores[bar_name] = 0.1

    print(f"📊 Step 3 - Bear signal triggered with scores: {bear_bar_scores}")
    executor.process_indicators(sell_tick, {}, bear_bar_scores)

    # Check results
    print(f"\n📋 RESULTS:")
    print(f"   Final position: {portfolio.position_size}")
    print(f"   Total trades: {len(portfolio.trade_history)}")
    print(f"   Trailing stop after sell: ${executor.trailing_stop_price:.2f}")

    if portfolio.position_size == 0 and len(portfolio.trade_history) == 2:
        buy_trade = portfolio.trade_history[0]
        sell_trade = portfolio.trade_history[1]
        profit = (sell_trade.price - buy_trade.price) * sell_trade.size
        print(f"   Buy: {buy_trade.size} @ ${buy_trade.price:.2f}")
        print(f"   Sell: {sell_trade.size} @ ${sell_trade.price:.2f}")
        print(f"   Profit: ${profit:.2f}")
        print("✅ SUCCESS: Bear signal sell executed!")
    else:
        print("❌ FAILED: Bear signal sell not working")


def test_trailing_stop_updates():
    """Test that trailing stop loss updates as price moves up"""

    # Load your JSON file
    json_file = "../../src/stock_analysis_ui/monitor_config_example_time_intervals.json"

    with open(json_file, 'r') as f:
        monitor_json = json.load(f)

    monitor_config = SimpleMonitorConfig(monitor_json)

    print(f"\n{'='*50}")
    print("TESTING TRAILING STOP UPDATES")
    print(f"{'='*50}")

    # Create portfolio and executor
    portfolio = Portfolio()
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.5
    )

    # Step 1: Buy at $150
    buy_tick = MockTickData(150.0)
    bull_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bull':
            bull_bar_scores[bar_name] = monitor_config.threshold + 0.1
        else:
            bull_bar_scores[bar_name] = 0.1

    executor.process_indicators(portfolio, buy_tick, {}, bull_bar_scores)
    initial_stop = executor.trailing_stop_price
    print(f"📊 Step 1 - Bought at $150.00, Stop: ${initial_stop:.2f}")

    # Step 2: Price moves to $155 (should update stop loss)
    no_signals = {bar_name: 0.1 for bar_name in monitor_config.bars.keys()}

    tick_155 = MockTickData(155.0)
    executor.process_indicators(portfolio, tick_155, {}, no_signals)
    stop_after_155 = executor.trailing_stop_price
    print(f"📊 Step 2 - Price $155.00, Stop: ${stop_after_155:.2f}")

    # Step 3: Price moves to $160 (should update stop again)
    tick_160 = MockTickData(160.0)
    executor.process_indicators(portfolio, tick_160, {}, no_signals)
    stop_after_160 = executor.trailing_stop_price
    print(f"📊 Step 3 - Price $160.00, Stop: ${stop_after_160:.2f}")

    # Step 4: Price drops to $158 (stop should NOT move down)
    tick_158 = MockTickData(158.0)
    executor.process_indicators(portfolio, tick_158, {}, no_signals)
    stop_after_158 = executor.trailing_stop_price
    print(f"📊 Step 4 - Price $158.00, Stop: ${stop_after_158:.2f}")

    # Check results
    print(f"\n📋 RESULTS:")
    print(f"   Initial stop ($150 entry): ${initial_stop:.2f}")
    print(f"   After $155: ${stop_after_155:.2f} {'✅' if stop_after_155 > initial_stop else '❌'}")
    print(f"   After $160: ${stop_after_160:.2f} {'✅' if stop_after_160 > stop_after_155 else '❌'}")
    print(f"   After $158: ${stop_after_158:.2f} {'✅' if stop_after_158 == stop_after_160 else '❌'}")

    if (stop_after_155 > initial_stop and
        stop_after_160 > stop_after_155 and
        stop_after_158 == stop_after_160):
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

    # Create portfolio and executor
    portfolio = Portfolio()
    executor = TradeExecutorSimple(
        monitor_config=monitor_config,
        default_position_size=100.0,
        stop_loss_pct=0.5
    )

    # Step 1: Buy first
    buy_tick = MockTickData(150.0)
    bull_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bull':
            bull_bar_scores[bar_name] = monitor_config.threshold + 0.1
        else:
            bull_bar_scores[bar_name] = 0.1

    executor.process_indicators(portfolio, buy_tick, {}, bull_bar_scores)
    print(f"📊 Step 1 - Bought: Position = {portfolio.position_size}")

    # Step 2: Price moves up, stop updates
    tick_155 = MockTickData(155.0)
    no_signals = {bar_name: 0.1 for bar_name in monitor_config.bars.keys()}
    executor.process_indicators(portfolio, tick_155, {}, no_signals)
    print(f"📊 Step 2 - Price up to $155: Stop = ${executor.trailing_stop_price:.2f}")

    # Step 3: Bear signal triggers
    sell_tick = MockTickData(157.0)
    bear_bar_scores = {}
    for bar_name, bar_config in monitor_config.bars.items():
        if bar_config.get('type') == 'bear':
            bear_bar_scores[bar_name] = monitor_config.bear_threshold + 0.1  # Above bear threshold
        else:
            bear_bar_scores[bar_name] = 0.1

    print(f"📊 Step 3 - Bear signal triggered with scores: {bear_bar_scores}")
    executor.process_indicators(portfolio, sell_tick, {}, bear_bar_scores)

    # Check results
    print(f"\n📋 RESULTS:")
    print(f"   Final position: {portfolio.position_size}")
    print(f"   Total trades: {len(portfolio.trade_history)}")
    print(f"   Trailing stop after sell: ${executor.trailing_stop_price:.2f}")

    if portfolio.position_size == 0 and len(portfolio.trade_history) == 2:
        buy_trade = portfolio.trade_history[0]
        sell_trade = portfolio.trade_history[1]
        profit = (sell_trade.price - buy_trade.price) * sell_trade.size
        print(f"   Buy: {buy_trade.size} @ ${buy_trade.price:.2f}")
        print(f"   Sell: {sell_trade.size} @ ${sell_trade.price:.2f}")
        print(f"   Profit: ${profit:.2f}")
        print("✅ SUCCESS: Bear signal sell executed!")
    else:
        print("❌ FAILED: Bear signal sell not working")


if __name__ == '__main__':
    test_simple_buy()
    test_trailing_stop_updates()
    test_bear_signal_sell()