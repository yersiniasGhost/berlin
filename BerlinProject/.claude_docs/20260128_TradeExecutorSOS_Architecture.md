# TradeExecutorSOS Architecture

## Overview

**TradeExecutorSOS** (Simultaneous Opposing Strategies) is a dual-account trade executor that maintains independent long and short positions simultaneously. The design achieves market-neutral exposure when both positions are active, with independent decision-making per account.

## Key Design Decisions

| Decision | Choice |
|----------|--------|
| Portfolio independence | Fully independent with shared reporting |
| Configuration | Two `TradeExecutorConfig` objects |
| Signal mapping | New `enter_short`/`exit_short` conditions |
| Neutral state | Both positions active (default on startup) |
| Position sizing | Equal between accounts |
| UI approach | Toggle: Long / Short / Combined views |
| GA optimization | Selected parameters only |
| Executor selection | By class name (like indicators) |

---

## 1. Data Models

### 1.1 New Configuration Model

```python
# models/monitor_configuration.py

class TradeExecutorSOSConfig(BaseModel):
    """Configuration for SOS (Simultaneous Opposing Strategies) executor"""

    # Shared settings
    default_position_size: float = PydanticField(default=100.0)

    # Long account configuration
    long_account: TradeExecutorConfig

    # Short account configuration
    short_account: TradeExecutorConfig
```

### 1.2 Extended MonitorConfiguration

```python
class MonitorConfiguration(BaseModel):
    # ... existing fields ...

    # Executor type selection (like indicators use indicator_class)
    executor_type: str = PydanticField(default="TradeExecutorUnified")

    # Existing unified executor config (for backwards compatibility)
    trade_executor: Optional[TradeExecutorConfig] = None

    # NEW: SOS executor config
    trade_executor_sos: Optional[TradeExecutorSOSConfig] = None

    # NEW: Short position conditions (parallel to enter_long/exit_long)
    enter_short: List[Dict[str, Any]] = PydanticField(default_factory=list)
    exit_short: List[Dict[str, Any]] = PydanticField(default_factory=list)
```

### 1.3 Validation Logic

```python
@model_validator(mode='before')
def validate_executor_config(cls, values):
    executor_type = values.get('executor_type', 'TradeExecutorUnified')

    if executor_type == 'TradeExecutorSOS':
        if 'trade_executor_sos' not in values:
            raise ValueError("TradeExecutorSOS requires trade_executor_sos configuration")
    else:
        if 'trade_executor' not in values:
            raise ValueError("trade_executor configuration required")

    return values
```

---

## 2. Core Executor Implementation

### 2.1 Class Structure

```python
# portfolios/trade_executor_sos.py

class TradeExecutorSOS:
    """
    Simultaneous Opposing Strategies Trade Executor

    Maintains two independent virtual accounts:
    - Long Account: Only takes long positions
    - Short Account: Only takes short positions

    Both accounts start with active positions (market neutral).
    Each account makes independent decisions based on its own parameters.
    """

    def __init__(self, monitor_config: MonitorConfiguration):
        self.monitor_config = monitor_config
        sos_config = monitor_config.trade_executor_sos

        # Shared position size (equal for both accounts)
        self.position_size = sos_config.default_position_size

        # Independent portfolios
        self.long_portfolio = Portfolio()
        self.short_portfolio = Portfolio()

        # Long account state
        self.long_config = sos_config.long_account
        self.long_stop_loss_price: Optional[float] = None
        self.long_take_profit_price: Optional[float] = None
        self.long_trailing_stop_price: Optional[float] = None
        self.long_highest_price: Optional[float] = None

        # Short account state
        self.short_config = sos_config.short_account
        self.short_stop_loss_price: Optional[float] = None
        self.short_take_profit_price: Optional[float] = None
        self.short_trailing_stop_price: Optional[float] = None
        self.short_lowest_price: Optional[float] = None  # For short trailing stop

        # Combined tracking
        self.trade_count = 0
        self.trade_details_history: Dict[int, Dict] = {}

        # Initialize both positions as active (market neutral start)
        self._initialized = False
```

### 2.2 Decision Flow

```python
def make_decision(self, tick: TickData, indicators: Dict[str, float],
                  bar_scores: Dict[str, float] = None) -> None:
    """
    Process tick for BOTH accounts independently
    """
    timestamp = int(tick.timestamp.timestamp() * 1000)
    current_price = tick.close
    bar_scores = defaultdict(float, bar_scores or {})

    # Initialize positions on first tick (market neutral start)
    if not self._initialized:
        self._initialize_positions(timestamp, current_price, bar_scores, indicators)
        self._initialized = True
        return

    # Process LONG account
    self._process_long_account(timestamp, current_price, bar_scores, tick.timestamp, indicators)

    # Process SHORT account
    self._process_short_account(timestamp, current_price, bar_scores, tick.timestamp, indicators)
```

### 2.3 Long Account Logic

```python
def _process_long_account(self, timestamp: int, price: float,
                          bar_scores: Dict, trade_time: datetime,
                          indicators: Dict) -> None:
    """Process long account decisions using enter_long/exit_long conditions"""

    # Update trailing stop if in position
    if self.long_portfolio.is_in_position() and self.long_config.trailing_stop_loss:
        self._update_long_trailing_stop(price)

    # Check exits first
    if self.long_portfolio.is_in_position():
        if self._check_long_exit_conditions(timestamp, price, bar_scores, trade_time, indicators):
            return

    # Check entries
    if not self.long_portfolio.is_in_position():
        if not self._has_long_signal_conflicts(bar_scores):
            self._check_long_entry_conditions(timestamp, price, bar_scores, trade_time, indicators)
```

### 2.4 Short Account Logic

```python
def _process_short_account(self, timestamp: int, price: float,
                           bar_scores: Dict, trade_time: datetime,
                           indicators: Dict) -> None:
    """Process short account decisions using enter_short/exit_short conditions"""

    # Update trailing stop if in position (inverted logic for shorts)
    if self.short_portfolio.is_in_position() and self.short_config.trailing_stop_loss:
        self._update_short_trailing_stop(price)

    # Check exits first
    if self.short_portfolio.is_in_position():
        if self._check_short_exit_conditions(timestamp, price, bar_scores, trade_time, indicators):
            return

    # Check entries
    if not self.short_portfolio.is_in_position():
        if not self._has_short_signal_conflicts(bar_scores):
            self._check_short_entry_conditions(timestamp, price, bar_scores, trade_time, indicators)
```

### 2.5 Short Position P&L (Inverted)

```python
def _calculate_short_pnl(self, entry_price: float, current_price: float) -> float:
    """
    Calculate P&L for short position (inverted from long)

    Short profit = entry_price - current_price (profit when price falls)
    """
    if entry_price == 0:
        return 0.0
    return ((entry_price - current_price) / entry_price) * 100.0
```

### 2.6 Combined Metrics

```python
def get_combined_metrics(self, current_price: float) -> Dict[str, Any]:
    """Get combined performance metrics for both accounts"""

    long_metrics = self.long_portfolio.get_performance_metrics(current_price)
    short_metrics = self.short_portfolio.get_performance_metrics(current_price)

    # Combined P&L
    combined_realized = (long_metrics['pnl']['realized_pnl_percent'] +
                        short_metrics['pnl']['realized_pnl_percent'])
    combined_unrealized = (long_metrics['pnl']['unrealized_pnl_percent'] +
                          short_metrics['pnl']['unrealized_pnl_percent'])

    # Net exposure
    long_exposure = self.position_size if self.long_portfolio.is_in_position() else 0
    short_exposure = -self.position_size if self.short_portfolio.is_in_position() else 0
    net_exposure = long_exposure + short_exposure

    return {
        'long': long_metrics,
        'short': short_metrics,
        'combined': {
            'realized_pnl_percent': combined_realized,
            'unrealized_pnl_percent': combined_unrealized,
            'total_pnl_percent': combined_realized + combined_unrealized,
            'net_exposure': net_exposure,
            'is_neutral': net_exposure == 0,
            'long_active': self.long_portfolio.is_in_position(),
            'short_active': self.short_portfolio.is_in_position()
        }
    }
```

---

## 3. Integration Points

### 3.1 DataStreamer Factory Pattern

```python
# data_streamer/data_streamer.py

from portfolios.trade_executor_unified import TradeExecutorUnified
from portfolios.trade_executor_sos import TradeExecutorSOS

EXECUTOR_REGISTRY = {
    'TradeExecutorUnified': TradeExecutorUnified,
    'TradeExecutorSOS': TradeExecutorSOS,
}

class DataStreamer:
    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration, ...):
        # ... existing init ...

        # Dynamic executor selection
        executor_type = getattr(monitor_config, 'executor_type', 'TradeExecutorUnified')
        executor_class = EXECUTOR_REGISTRY.get(executor_type, TradeExecutorUnified)
        self.trade_executor = executor_class(monitor_config)
```

### 3.2 External Tool Interface

The `ExternalTool.process_tick()` needs extended metrics:

```python
def process_tick(self, ..., portfolio_metrics: Dict, ...):
    """
    portfolio_metrics now contains:
    - For Unified: standard metrics
    - For SOS: {long: {...}, short: {...}, combined: {...}}
    """
```

### 3.3 BTDataStreamer (Backtesting)

Same factory pattern applies to `BTDataStreamer` for GA optimization.

---

## 4. UI Changes

### 4.1 Configuration Form

New file: `templates/components/_trade_executor_sos_form.html`

```html
<!-- Executor Type Selector -->
<div class="mb-3">
    <label class="form-label">Executor Type</label>
    <select id="executorType" class="form-select" onchange="toggleExecutorForm()">
        <option value="TradeExecutorUnified">Unified (Single Direction)</option>
        <option value="TradeExecutorSOS">SOS (Long + Short)</option>
    </select>
</div>

<!-- SOS Configuration (shown when SOS selected) -->
<div id="sosConfigContainer" style="display: none;">
    <div class="row">
        <!-- Long Account Column -->
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-success text-white">
                    <h6 class="mb-0">📈 Long Account</h6>
                </div>
                <div class="card-body">
                    {% include 'components/_account_config_fields.html' with account='long' %}
                </div>
            </div>
        </div>

        <!-- Short Account Column -->
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-danger text-white">
                    <h6 class="mb-0">📉 Short Account</h6>
                </div>
                <div class="card-body">
                    {% include 'components/_account_config_fields.html' with account='short' %}
                </div>
            </div>
        </div>
    </div>

    <!-- Shared Position Size -->
    <div class="mt-3">
        <label class="form-label">Shared Position Size</label>
        <input type="number" id="sosPositionSize" class="form-control" style="max-width: 200px;">
    </div>
</div>
```

### 4.2 Conditions Editor

Extend existing bar/condition editor to support:
- `enter_long` / `exit_long` (existing)
- `enter_short` / `exit_short` (new)

```html
<!-- Condition Type Tabs (shown for SOS) -->
<ul class="nav nav-tabs" id="conditionTabs">
    <li class="nav-item">
        <a class="nav-link active" data-bs-toggle="tab" href="#longConditions">Long Conditions</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" data-bs-toggle="tab" href="#shortConditions">Short Conditions</a>
    </li>
</ul>
```

### 4.3 Performance Dashboard

View toggle for SOS executor:

```html
<!-- View Toggle (shown for SOS) -->
<div class="btn-group mb-3" id="sosViewToggle">
    <button class="btn btn-outline-success active" data-view="long">📈 Long</button>
    <button class="btn btn-outline-danger" data-view="short">📉 Short</button>
    <button class="btn btn-outline-primary" data-view="combined">📊 Combined</button>
</div>

<!-- Net Exposure Indicator -->
<div class="alert" id="exposureIndicator">
    <span id="exposureStatus"></span>
    <span class="badge" id="exposureBadge"></span>
</div>
```

### 4.4 JavaScript Updates

```javascript
// static/js/sos-executor.js

function updateSOSMetrics(metrics) {
    const view = getCurrentView(); // 'long' | 'short' | 'combined'

    if (view === 'combined') {
        updateCombinedView(metrics.combined);
    } else {
        updateAccountView(metrics[view], view);
    }

    // Always update exposure indicator
    updateExposureIndicator(metrics.combined);
}

function updateExposureIndicator(combined) {
    const indicator = document.getElementById('exposureIndicator');
    const badge = document.getElementById('exposureBadge');

    if (combined.is_neutral) {
        indicator.className = 'alert alert-info';
        badge.textContent = 'NEUTRAL';
        badge.className = 'badge bg-info';
    } else if (combined.net_exposure > 0) {
        indicator.className = 'alert alert-success';
        badge.textContent = 'NET LONG';
        badge.className = 'badge bg-success';
    } else {
        indicator.className = 'alert alert-danger';
        badge.textContent = 'NET SHORT';
        badge.className = 'badge bg-danger';
    }
}
```

---

## 5. JSON Configuration Schema

### 5.1 Example Monitor Config with SOS

```json
{
    "monitor": {
        "name": "SOS Strategy - Tech Stocks",
        "description": "Market-neutral strategy with independent long/short signals",
        "executor_type": "TradeExecutorSOS",

        "trade_executor_sos": {
            "default_position_size": 100,

            "long_account": {
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.03,
                "take_profit_type": "percent",
                "trailing_stop_loss": true,
                "trailing_stop_distance_pct": 0.015,
                "trailing_stop_activation_pct": 0.01,
                "ignore_bear_signals": false
            },

            "short_account": {
                "stop_loss_pct": 0.025,
                "take_profit_pct": 0.025,
                "take_profit_type": "percent",
                "trailing_stop_loss": false,
                "trailing_stop_distance_pct": 0.01,
                "trailing_stop_activation_pct": 0.005,
                "ignore_bear_signals": false
            }
        },

        "enter_long": [
            {"name": "bull_momentum_bar", "threshold": 0.7}
        ],
        "exit_long": [
            {"name": "bear_reversal_bar", "threshold": 0.6}
        ],
        "enter_short": [
            {"name": "bear_breakdown_bar", "threshold": 0.7}
        ],
        "exit_short": [
            {"name": "bull_reversal_bar", "threshold": 0.6}
        ],

        "bars": {
            "bull_momentum_bar": {
                "type": "bull",
                "indicators": {"rsi_oversold": 1.0, "macd_cross_up": 0.8}
            },
            "bear_reversal_bar": {
                "type": "bear",
                "indicators": {"rsi_overbought": 1.0}
            },
            "bear_breakdown_bar": {
                "type": "bear",
                "indicators": {"rsi_overbought": 1.0, "macd_cross_down": 0.8}
            },
            "bull_reversal_bar": {
                "type": "bull",
                "indicators": {"rsi_oversold": 1.0}
            }
        }
    },
    "indicators": [...]
}
```

---

## 6. File Structure

```
src/
├── portfolios/
│   ├── trade_executor_unified.py    # Existing
│   ├── trade_executor_sos.py        # NEW: SOS executor
│   └── portfolio_tool.py            # Existing (may need short P&L methods)
│
├── models/
│   ├── monitor_configuration.py     # MODIFY: Add SOS config, enter_short/exit_short
│   └── validation/
│       └── monitor_validators.py    # MODIFY: Add SOS validation
│
├── data_streamer/
│   └── data_streamer.py             # MODIFY: Executor factory pattern
│
├── optimization/
│   └── calculators/
│       └── bt_data_streamer.py      # MODIFY: Same factory pattern
│
└── visualization_apps/
    ├── templates/
    │   └── components/
    │       ├── _trade_executor_form.html       # Existing
    │       ├── _trade_executor_sos_form.html   # NEW
    │       └── _account_config_fields.html     # NEW: Reusable account fields
    │
    └── static/js/
        ├── monitor-config.js        # MODIFY: SOS support
        └── sos-executor.js          # NEW: SOS-specific UI logic
```

---

## 7. Implementation Phases

### Phase 1: Core Models
1. Add `TradeExecutorSOSConfig` to `monitor_configuration.py`
2. Add `enter_short`/`exit_short` fields
3. Add `executor_type` field with validation
4. Update model validators

### Phase 2: Executor Implementation
1. Create `trade_executor_sos.py` with dual portfolio logic
2. Implement short position P&L calculations
3. Add combined metrics method
4. Ensure same interface as `TradeExecutorUnified`

### Phase 3: Integration
1. Add executor registry/factory to `DataStreamer`
2. Update `BTDataStreamer` for optimization
3. Update `ExternalTool` interface for SOS metrics

### Phase 4: UI - Configuration
1. Create SOS configuration form components
2. Add executor type selector
3. Add short condition editors
4. Update JSON save/load logic

### Phase 5: UI - Visualization
1. Add view toggle for Long/Short/Combined
2. Add net exposure indicator
3. Update charts for dual-account display
4. Update trade history tables

### Phase 6: GA Optimization
1. Update parameter mapping for SOS config
2. Ensure selected parameters work for both accounts
3. Test optimization with SOS executor

---

## 8. Open Questions for Implementation

1. **Short Portfolio Extension**: Should `Portfolio` class get explicit short methods, or reuse existing with sign conventions?

2. **Trade History Format**: Should SOS trade history indicate which account (`long_entry`, `short_exit`, etc.)?

3. **Initialization Price**: On startup, what price should be used for initial position entry? First tick price?

4. **WebSocket Messages**: Should SOS send separate messages per account or combined payload?
