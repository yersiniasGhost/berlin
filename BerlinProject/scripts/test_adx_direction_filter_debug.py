#!/usr/bin/env python3
"""
Debug script to test ADXTrendIndicator direction_filter behavior with real NVDA data.
Tests all three filter modes (Both, Bull, Bear) and shows where they differ.
"""

import numpy as np
from datetime import datetime
from typing import List, Dict
import sys

# Add project to path
sys.path.insert(0, '/home/yersinia/devel/berlin/BerlinProject/src')

from models.tick_data import TickData
from indicator_triggers.indicator_base import IndicatorConfiguration, IndicatorType
from indicator_triggers.trend_indicators import ADXTrendIndicator
from candle_aggregator.csa_container import CSAContainer


def load_nvda_candles(start_date: str, end_date: str, agg_config: str = "5m-normal") -> List[TickData]:
    """Load NVDA candle data using CSAContainer."""
    print(f"Loading NVDA data from {start_date} to {end_date} with {agg_config}...")

    data_config = {
        'ticker': 'NVDA',
        'start_date': start_date,
        'end_date': end_date,
        'include_extended_hours': True
    }

    csa_container = CSAContainer(data_config, [agg_config])
    aggregator = csa_container.get_aggregator(agg_config)

    if aggregator is None:
        print(f"No aggregator found for {agg_config}")
        return []

    candles = aggregator.get_history()
    print(f"Loaded {len(candles)} candles")
    return candles


def create_adx_indicator(direction_filter: str) -> ADXTrendIndicator:
    """Create ADX indicator with specified direction filter."""
    config = IndicatorConfiguration(
        indicator_name='ADXTrendIndicator',
        display_name='ADX Trend',
        parameters={
            'period': 14,
            'trend_threshold': 25,
            'strong_trend_threshold': 40,
            'direction_filter': direction_filter
        }
    )
    return ADXTrendIndicator(config)




def test_direction_filters(tick_data: List[TickData]):
    """Test all three direction filters and compare results."""

    print("\n" + "="*100)
    print("ADX TREND INDICATOR - DIRECTION FILTER ANALYSIS")
    print("="*100)

    # Verify ADX is a TREND indicator
    print(f"\nADXTrendIndicator type: {ADXTrendIndicator.get_indicator_type()}")
    print(f"Is TREND indicator: {ADXTrendIndicator.get_indicator_type() == IndicatorType.TREND}")

    # Calculate for all three filters
    results = {}
    for filter_type in ['Both', 'Bull', 'Bear']:
        indicator = create_adx_indicator(filter_type)
        print(f"\nCalculating with direction_filter='{filter_type}'...")
        print(f"  Parameter check: {indicator.get_parameter('direction_filter')}")

        values, components = indicator.calculate(tick_data)
        results[filter_type] = {
            'values': values,
            'plus_di': components.get('adx_trend_plus_di', np.zeros(len(values))),
            'minus_di': components.get('adx_trend_minus_di', np.zeros(len(values))),
            'adx': components.get('adx_trend_adx', np.zeros(len(values)))
        }

        # Summary stats
        non_nan = ~np.isnan(values)
        non_zero = values[non_nan] != 0
        positive = values[non_nan] > 0
        negative = values[non_nan] < 0

        print(f"  Total values: {len(values)}")
        print(f"  Non-NaN: {np.sum(non_nan)}")
        print(f"  Non-zero: {np.sum(non_zero)}")
        print(f"  Positive: {np.sum(positive)}")
        print(f"  Negative: {np.sum(negative)}")
        print(f"  Zero: {np.sum(~non_zero)}")

    # Analyze market conditions
    print("\n" + "="*100)
    print("MARKET CONDITION ANALYSIS")
    print("="*100)

    plus_di = results['Both']['plus_di']
    minus_di = results['Both']['minus_di']
    adx = results['Both']['adx']

    valid = ~(np.isnan(plus_di) | np.isnan(minus_di))
    bullish = (plus_di > minus_di) & valid
    bearish = (minus_di > plus_di) & valid
    strong_trend = (adx >= 25) & valid
    weak_trend = (adx < 25) & valid

    print(f"\nMarket periods:")
    print(f"  Bullish (+DI > -DI): {np.sum(bullish)}")
    print(f"  Bearish (-DI > +DI): {np.sum(bearish)}")
    print(f"  Strong trend (ADX >= 25): {np.sum(strong_trend)}")
    print(f"  Weak trend (ADX < 25): {np.sum(weak_trend)}")

    # Show detailed comparison
    print("\n" + "="*100)
    print("DETAILED COMPARISON - Sample periods")
    print("="*100)

    print(f"\n{'Idx':<6} {'Time':<20} {'+DI':<8} {'-DI':<8} {'ADX':<8} {'Market':<10} {'Both':<10} {'Bull':<10} {'Bear':<10} {'Notes'}")
    print("-"*110)

    both_vals = results['Both']['values']
    bull_vals = results['Bull']['values']
    bear_vals = results['Bear']['values']

    issues = []

    # Sample every Nth value to show variety
    step = max(1, len(tick_data) // 50)

    for i in range(14, len(tick_data), step):  # Skip first 14 (ADX warmup)
        if np.isnan(plus_di[i]) or np.isnan(minus_di[i]):
            continue

        pdi = plus_di[i]
        mdi = minus_di[i]
        adx_v = adx[i]
        both_v = both_vals[i]
        bull_v = bull_vals[i]
        bear_v = bear_vals[i]

        market = 'BULLISH' if pdi > mdi else 'BEARISH'
        ts = tick_data[i].timestamp.strftime('%m/%d %H:%M') if i < len(tick_data) else '?'

        notes = []

        # Check for issues
        if market == 'BULLISH':
            if bull_v != both_v and both_v > 0:
                notes.append('Bull!=Both')
                issues.append(f"Idx {i}: Bull should equal Both in bullish")
            if bear_v != 0 and both_v > 0:
                notes.append('Bear!=0')
                issues.append(f"Idx {i}: Bear should be 0 in bullish")
        else:  # BEARISH
            if bear_v != both_v and both_v < 0:
                notes.append('Bear!=Both')
                issues.append(f"Idx {i}: Bear should equal Both in bearish")
            if bull_v != 0 and both_v < 0:
                notes.append('Bull!=0')
                issues.append(f"Idx {i}: Bull should be 0 in bearish")

        if adx_v < 25:
            notes.append('ADX<25')

        notes_str = ', '.join(notes) if notes else ''

        print(f"{i:<6} {ts:<20} {pdi:<8.2f} {mdi:<8.2f} {adx_v:<8.2f} {market:<10} {both_v:<10.4f} {bull_v:<10.4f} {bear_v:<10.4f} {notes_str}")

    # Summary
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)

    if issues:
        print(f"\n*** FOUND {len(issues)} ISSUES ***")
        for issue in issues[:10]:
            print(f"  - {issue}")
    else:
        print("\n✓ No logic issues found - direction filters working correctly")

    # Explain expected behavior
    print("\n" + "="*100)
    print("EXPECTED BEHAVIOR EXPLANATION")
    print("="*100)
    print("""
In a BULLISH market (+DI > -DI):
  - Both:  Positive value (e.g., +0.5)
  - Bull:  Positive value (same as Both)
  - Bear:  0 (filters out bullish signals)

  --> Both and Bull will show SAME VALUES when market is bullish!

In a BEARISH market (-DI > +DI):
  - Both:  Negative value (e.g., -0.5)
  - Bull:  0 (filters out bearish signals)
  - Bear:  Negative value (same as Both)

  --> Both and Bear will show SAME VALUES when market is bearish!

When ADX < 25 (weak trend):
  - All filters return 0 (trend not strong enough)
""")

    # Final analysis
    bullish_count = np.sum(bullish)
    bearish_count = np.sum(bearish)

    if bullish_count > bearish_count * 2:
        print(f"\n*** YOUR DATA IS MOSTLY BULLISH ({bullish_count} bullish vs {bearish_count} bearish) ***")
        print("This explains why Both and Bull show the same results most of the time!")
        print("Bear will mostly show 0 because it filters out bullish signals.")


def main():
    # Load NVDA data using CSAContainer (same as visualization app)
    start_date = "2026-01-07"
    end_date = "2026-01-22"
    agg_config = "5m-normal"  # Matching the monitor config

    candles = load_nvda_candles(start_date, end_date, agg_config)

    if len(candles) == 0:
        print("\n*** No data loaded ***")
        return

    if len(candles) < 20:
        print(f"Not enough data for ADX calculation (need at least 20 candles, got {len(candles)})")
        return

    # Test the direction filters
    test_direction_filters(candles)


if __name__ == '__main__':
    main()
