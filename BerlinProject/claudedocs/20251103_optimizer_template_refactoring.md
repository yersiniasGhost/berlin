# Optimizer Template Refactoring

**Date**: 2025-11-03
**Status**: HTML/CSS Complete, JavaScript Pending

## Overview

Refactored `/src/visualization_apps/templates/optimizer/main.html` (2580 lines) into modular, maintainable components.

## What Was Completed

### 1. CSS Extraction ✅
**File**: `src/visualization_apps/static/css/optimizer.css`
- Extracted 98 lines of inline styles
- Organized into logical sections (cards, buttons, forms)
- Ready to use with `<link>` tag

### 2. HTML Component Splitting ✅
**Directory**: `src/visualization_apps/templates/optimizer/components/`

Created 6 modular template components:

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| File Selector | `_file_selector.html` | 48 | Upload monitor/data/GA config files |
| Config Editor | `_config_editor.html` | 287 | Tabbed configuration editor with all config tabs |
| Control Panel | `_control_panel.html` | 40 | Start/pause/stop buttons and progress bar |
| Charts Section | `_charts_section.html` | 165 | All 6 chart containers in responsive grid |
| Test Evaluations | `_test_evaluations.html` | 38 | Test data performance table |
| Elite Modal | `_elite_modal.html` | 45 | Elite selection modal for replay |

### 3. Main Template Refactored ✅
**File**: `src/visualization_apps/templates/optimizer/main_refactored.html`
- Clean 60-line template using Jinja2 `{% include %}` directives
- All components properly referenced
- CSS linked externally
- JavaScript section documented but not yet split

## What Remains: JavaScript Refactoring

### Current State
The original `main.html` contains ~1836 lines of inline JavaScript (lines 744-2580). This massive script needs to be split into modular files.

### Recommended JavaScript Structure

```
src/visualization_apps/static/js/optimizer/
├── websocket.js          # WebSocket connection and event handlers (~400 lines)
├── charts.js             # Chart initialization and updates (~500 lines)
├── controls.js           # Button handlers and UI controls (~300 lines)
├── parameters.js         # Parameter histogram and evolution (~400 lines)
├── test-eval.js          # Test evaluations table updates (~100 lines)
├── replay.js             # Send to replay functionality (~100 lines)
└── main.js               # Main initialization and module coordination (~36 lines)
```

### JavaScript Module Breakdown

#### 1. `websocket.js`
**Lines**: Original 758-1846 (~1088 lines)
**Responsibilities**:
- WebSocket connection initialization
- Event handlers for optimization updates
- Message parsing and dispatching
- Connection error handling
- Reconnection logic

**Key Functions**:
```javascript
// Initialize WebSocket
function initializeWebSocket() { ... }

// Event: New generation data
socket.on('new_generation', function(data) { ... });

// Event: Optimization complete
socket.on('optimization_complete', function(data) { ... });

// Event: Parameter updates
socket.on('parameter_update', function(data) { ... });
```

#### 2. `charts.js`
**Lines**: Original 1847-2143 (~296 lines)
**Responsibilities**:
- Plotly chart initialization
- Chart update functions
- Chart clearing/reset
- Responsive layout handling

**Key Functions**:
```javascript
// Initialize all charts
function initializeCharts() { ... }

// Update objective evolution chart
function updateObjectiveChart(data) { ... }

// Update parallel coordinates
function updateParallelCoordinatesChart(data) { ... }

// Update best strategy candlestick
function updateBestStrategyChart(data) { ... }

// Update trade distribution charts
function updateTradeDistributionCharts(winData, loseData) { ... }

// Clear all charts
function clearAllCharts() { ... }
```

#### 3. `controls.js`
**Lines**: Original 845-1027, 1957-2028 (~254 lines)
**Responsibilities**:
- Button click handlers
- Button state management (enable/disable)
- Progress bar updates
- Configuration file loading
- Save/load functionality

**Key Functions**:
```javascript
// Start optimization
document.getElementById('startOptimizerBtn').onclick = function() { ... }

// Pause optimization
document.getElementById('pauseOptimizerBtn').onclick = function() { ... }

// Stop optimization
document.getElementById('stopOptimizerBtn').onclick = function() { ... }

// Load configurations
document.getElementById('loadConfigsBtn').onclick = function() { ... }

// Save optimized configs
document.getElementById('saveOptimizedConfigsBtn').onclick = function() { ... }

// Load elite to forms
document.getElementById('loadEliteToFormsBtn').onclick = function() { ... }

// Update button states
function updateButtonStates(state) { ... }
```

#### 4. `parameters.js`
**Lines**: Original 2144-2411 (~267 lines)
**Responsibilities**:
- Parameter histogram generation
- Parameter evolution tracking
- Convergence detection
- Parameter selector dropdown population

**Key Functions**:
```javascript
// Update parameter histogram
function updateParameterHistogram(data) { ... }

// Update parameter evolution chart
function updateParameterEvolution(data) { ... }

// Populate parameter selector
function populateParameterSelector(parameters) { ... }

// Detect convergence
function detectConvergence(evolutionData) { ... }

// Handle parameter selection change
document.getElementById('parameterSelector').onchange = function() { ... }
```

#### 5. `test-eval.js`
**Lines**: Original 2412-2479 (~67 lines)
**Responsibilities**:
- Test evaluations table updates
- Overfitting detection
- Performance comparison display

**Key Functions**:
```javascript
// Update test evaluations table
function updateTestEvaluationsTable(data) { ... }

// Calculate overfitting metric
function calculateOverfitting(trainPnL, testPnL) { ... }

// Show/hide test evaluations section
function toggleTestEvaluationsSection(show) { ... }
```

#### 6. `replay.js`
**Lines**: Original 2480-2550 (~70 lines)
**Responsibilities**:
- Elite selection modal handling
- Send to replay functionality
- Elite data formatting

**Key Functions**:
```javascript
// Show elite selection modal
document.getElementById('sendToReplayBtn').onclick = function() { ... }

// Populate elite selection table
function populateEliteSelectionTable(elites) { ... }

// Send selected elite to replay
document.getElementById('confirmSendToReplayBtn').onclick = function() { ... }
```

#### 7. `main.js`
**Responsibilities**:
- Module initialization coordinator
- Page load event handler
- Global state management

**Structure**:
```javascript
// Import or coordinate all modules
document.addEventListener('DOMContentLoaded', function() {
    // Initialize WebSocket
    initializeWebSocket();

    // Initialize charts
    initializeCharts();

    // Setup control handlers
    setupControlHandlers();

    // Setup parameter tracking
    setupParameterTracking();

    // Setup test evaluations
    setupTestEvaluations();

    // Setup replay functionality
    setupReplayFunctionality();
});
```

## Migration Steps

### Step 1: Create JavaScript Module Files
```bash
mkdir -p src/visualization_apps/static/js/optimizer
touch src/visualization_apps/static/js/optimizer/{websocket,charts,controls,parameters,test-eval,replay,main}.js
```

### Step 2: Extract WebSocket Code
- Copy lines 758-1846 from original `main.html`
- Remove wrapping `<script>` tags
- Extract socket event handlers
- Add module export if using ES6 modules

### Step 3: Extract Chart Code
- Copy lines 1847-2143
- Extract chart initialization functions
- Extract chart update functions
- Add Plotly dependency management

### Step 4: Extract Control Code
- Copy button handler code (lines 845-1027, 1957-2028)
- Extract file upload handlers
- Extract configuration management
- Add button state management

### Step 5: Extract Parameter Code
- Copy lines 2144-2411
- Extract histogram generation
- Extract evolution tracking
- Add parameter selector handling

### Step 6: Extract Test Evaluation Code
- Copy lines 2412-2479
- Extract table update logic
- Add overfitting calculations

### Step 7: Extract Replay Code
- Copy lines 2480-2550
- Extract modal handling
- Add elite selection logic

### Step 8: Create Main Coordinator
- Create initialization sequence
- Add error handling
- Setup global state if needed

### Step 9: Update Template
- Replace the placeholder script block in `main_refactored.html`
- Add script tags for each module:
```html
<script src="{{ url_for('static', filename='js/optimizer/websocket.js') }}"></script>
<script src="{{ url_for('static', filename='js/optimizer/charts.js') }}"></script>
<script src="{{ url_for('static', filename='js/optimizer/controls.js') }}"></script>
<script src="{{ url_for('static', filename='js/optimizer/parameters.js') }}"></script>
<script src="{{ url_for('static', filename='js/optimizer/test-eval.js') }}"></script>
<script src="{{ url_for('static', filename='js/optimizer/replay.js') }}"></script>
<script src="{{ url_for('static', filename='js/optimizer/main.js') }}"></script>
```

### Step 10: Test Thoroughly
- Test all button functionality
- Test WebSocket connection and updates
- Test chart rendering and updates
- Test parameter histogram and evolution
- Test test evaluations display
- Test replay functionality
- Check console for errors

## Benefits of Refactoring

### Before
- **Single File**: 2580 lines
- **Maintainability**: Very difficult
- **Code Navigation**: Ctrl+F only
- **Reusability**: None
- **Testing**: Nearly impossible
- **Collaboration**: High merge conflict risk

### After
- **Multiple Files**: 7 HTML components + 7 JS modules + 1 CSS file = 15 files
- **Maintainability**: Easy to find and fix issues
- **Code Navigation**: File-based organization
- **Reusability**: Components can be reused
- **Testing**: Each module can be tested independently
- **Collaboration**: Low merge conflict risk

## File Size Comparison

| Component | Original | Refactored | Reduction |
|-----------|----------|------------|-----------|
| CSS | Inline (103 lines) | External (98 lines) | ✅ Separated |
| HTML | Single file (2580 lines) | 7 files (623 lines total) | ✅ 76% reduction per file |
| JavaScript | Inline (1836 lines) | 7 files (~262 lines avg) | ✅ 86% reduction per file |

## Usage Instructions

### Current Usage (Until JS Refactored)
The original `main.html` still works and should be used until JavaScript refactoring is complete.

### After Complete Refactoring
```bash
# Backup original
mv src/visualization_apps/templates/optimizer/main.html \
   src/visualization_apps/templates/optimizer/main_original_backup.html

# Use refactored version
mv src/visualization_apps/templates/optimizer/main_refactored.html \
   src/visualization_apps/templates/optimizer/main.html
```

## Notes
- All HTML components have been tested for proper Jinja2 syntax
- CSS has been extracted and is ready to use
- JavaScript refactoring is the only remaining task
- Original file has been preserved for reference
- No functionality should be lost in the refactoring

## Next Steps
1. Create JavaScript module directory structure
2. Extract JavaScript following the module breakdown above
3. Test each module independently
4. Test integrated system
5. Switch to refactored template
6. Archive original file
