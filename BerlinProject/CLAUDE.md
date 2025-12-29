# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BerlinProject (MLF-TA) is a Python-based algorithmic trading platform combining:
- Real-time and historical data streaming from multiple brokers (Schwab, IBKR)
- Technical indicator calculation with 20+ indicators
- Genetic algorithm optimization for strategy parameters
- Web-based dashboards for live trading and backtesting

## Development Environment

```bash
conda activate mlf
pip install -e .  # Install package in development mode
```

## Running the Applications

**Optimization/Visualization UI** (port 5003):
```bash
cd src/visualization_apps
python app.py
# Access at http://localhost:5003/optimizer
```

**Live Trading Dashboard**:
```bash
cd src/stock_analysis_ui
python app.py                                           # Live mode (browser auth)
python app.py --replay-file data.csv --symbol NVDA      # Single symbol replay
python app.py --replay-files NVDA:nvda.csv AAPL:aapl.csv  # Multi-symbol replay
```

## Running Tests

Tests are in `tests/` mirroring `src/` structure. Most tests are standalone scripts:
```bash
cd tests/data_streamer
python test_candle_aggregator.py
```

## Architecture

### Data Flow
```
Broker/CSV → DataLink → DataStreamer → CandleAggregator → IndicatorProcessor → TradeExecutor
```

### Key Modules (src/)

| Module | Purpose |
|--------|---------|
| `data_streamer/` | Real-time tick processing, candle aggregation, indicator calculation |
| `optimization/` | Genetic algorithm framework with fitness calculators and backtest infrastructure |
| `indicator_triggers/` | Technical indicators (IndicatorBase, ParameterSpec) - all return `(values, timestamps)` tuples |
| `portfolios/` | Trade execution logic (TradeExecutorUnified) with position management |
| `models/` | Pydantic models (MonitorConfiguration, TickData, DataContainer) |
| `mlf_utils/` | Shared utilities (LogManager singleton, CacheManager, error handlers) |
| `visualization_apps/` | Flask+SocketIO optimizer UI with real-time GA progress |
| `stock_analysis_ui/` | Flask+SocketIO live trading dashboard |

### Core Abstractions

**Indicators**: Inherit from `IndicatorBase`, use `ParameterSpec` for UI-aware parameters. All `calculate()` methods must return `(values, timestamps)` tuple.

**Optimization**: `ProblemDomain` → `Individual` → `FitnessCalculator` pattern. `MlfProblem` defines trading parameter optimization.

**Configuration**: `MonitorConfiguration` (Pydantic) defines complete strategy with indicators, bars, entry/exit conditions.

**Logging**: Use `LogManager` singleton - `logger = LogManager("mlf.log").get_logger("module_name")`

### Data Sources (Pluggable DataLinks)
- `SchwabDataLink` - Live Schwab API
- `IBKRDataLink` - Interactive Brokers
- `CSReplayDataLink` - Historical CSV replay for backtesting

## Environment Configuration

Environment variables loaded from `~/.mlf/.env`:
- MongoDB connection settings
- Broker credentials (Schwab, IBKR)
- Data provider selection
- Logging configuration

## Directory Conventions

| Directory | Purpose |
|-----------|---------|
| `inputs/` | Input data files for backtesting |
| `outputs/` | Timestamped optimization results |
| `monitors/` | Strategy configuration JSON files |
| `indicator_configs/` | Indicator definition files |
| `uploads/` | Web UI file uploads |
