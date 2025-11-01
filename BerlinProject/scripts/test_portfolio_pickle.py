#!/usr/bin/env python3
"""
Test script to verify Portfolio and related objects are pickleable.
"""

import pickle
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from portfolios.portfolio_tool import Portfolio, Trade, TradeReason


def test_trade_pickle():
    """Test if Trade is pickleable"""
    print("Testing Trade pickling...")
    trade = Trade(
        time=1234567890,
        size=100.0,
        price=150.50,
        reason=TradeReason.ENTER_LONG
    )

    try:
        pickled = pickle.dumps(trade)
        unpickled = pickle.loads(pickled)

        assert unpickled.time == trade.time
        assert unpickled.size == trade.size
        assert unpickled.price == trade.price
        assert unpickled.reason == trade.reason

        print("✅ Trade is pickleable")
        return True
    except Exception as e:
        print(f"❌ Trade is NOT pickleable: {e}")
        return False


def test_portfolio_pickle():
    """Test if Portfolio is pickleable"""
    print("\nTesting Portfolio pickling...")

    # Create a portfolio with some trades
    portfolio = Portfolio()
    portfolio.buy(time=1000, price=100.0, reason=TradeReason.ENTER_LONG, size=50.0)
    portfolio.exit_long(time=2000, price=105.0, reason=TradeReason.EXIT_LONG)
    portfolio.buy(time=3000, price=102.0, reason=TradeReason.ENTER_LONG, size=50.0)
    portfolio.exit_long(time=4000, price=98.0, reason=TradeReason.STOP_LOSS)

    print(f"Portfolio has {len(portfolio.trade_history)} trades")
    print(f"Total P&L: {portfolio.total_realized_pnl_percent:.4f}")

    try:
        pickled = pickle.dumps(portfolio)
        unpickled = pickle.loads(pickled)

        assert len(unpickled.trade_history) == len(portfolio.trade_history)
        assert unpickled.position_size == portfolio.position_size
        assert unpickled.total_realized_pnl_percent == portfolio.total_realized_pnl_percent

        print("✅ Portfolio is pickleable")
        print(f"Pickle size: {len(pickled)} bytes")
        return True
    except Exception as e:
        print(f"❌ Portfolio is NOT pickleable: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_portfolio_with_many_trades():
    """Test portfolio with realistic number of trades"""
    print("\nTesting Portfolio with many trades...")

    portfolio = Portfolio()

    # Simulate 100 trades
    for i in range(100):
        entry_price = 100.0 + i * 0.5
        exit_price = entry_price + (1.0 if i % 3 == 0 else -0.5)

        portfolio.buy(
            time=1000 + i * 1000,
            price=entry_price,
            reason=TradeReason.ENTER_LONG,
            size=50.0
        )
        portfolio.exit_long(
            time=1000 + i * 1000 + 500,
            price=exit_price,
            reason=TradeReason.EXIT_LONG
        )

    print(f"Portfolio has {len(portfolio.trade_history)} trades")

    try:
        pickled = pickle.dumps(portfolio)
        unpickled = pickle.loads(pickled)

        assert len(unpickled.trade_history) == 200  # 100 buys + 100 exits

        print("✅ Portfolio with many trades is pickleable")
        print(f"Pickle size: {len(pickled)} bytes ({len(pickled)/1024:.2f} KB)")
        return True
    except Exception as e:
        print(f"❌ Portfolio with many trades is NOT pickleable: {e}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("PORTFOLIO PICKLE COMPATIBILITY TEST")
    print("=" * 60)

    results = []
    results.append(("Trade", test_trade_pickle()))
    results.append(("Portfolio", test_portfolio_pickle()))
    results.append(("Portfolio (many trades)", test_portfolio_with_many_trades()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n🎉 All pickle tests PASSED - Portfolio is fully pickleable!")
        sys.exit(0)
    else:
        print("\n❌ Some tests FAILED - Portfolio may not be pickleable")
        sys.exit(1)
