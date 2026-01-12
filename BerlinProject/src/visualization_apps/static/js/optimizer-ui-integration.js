/**
 * Optimizer UI Integration
 * Bridges the WebSocket manager with the existing UI components
 */

class OptimizerUIIntegration {
    constructor() {
        this.charts = {};
        this.optimizationRunning = false;
        this.pollInterval = null;
        this.addedGenerations = new Set();
        this.connectionIndicator = null;
    }

    /**
     * Initialize UI integration
     */
    init() {
        console.log('🎨 Initializing Optimizer UI Integration');

        // Create connection status indicator
        this.createConnectionIndicator();

        // Setup WebSocket event handlers
        this.setupWebSocketHandlers();

        // Setup button handlers
        this.setupButtonHandlers();

        // Connect WebSocket
        window.optimizerWS.connect();
    }

    /**
     * Create connection status indicator in UI
     */
    createConnectionIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'connection-indicator';
        indicator.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 20px;
            border-radius: 5px;
            font-weight: bold;
            z-index: 9999;
            display: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        `;
        document.body.appendChild(indicator);
        this.connectionIndicator = indicator;
    }

    /**
     * Update connection indicator
     */
    updateConnectionIndicator(state, message) {
        const indicator = this.connectionIndicator;
        if (!indicator) return;

        const states = {
            connected: { bg: '#28a745', text: '✅ Connected', display: 'none' },
            connecting: { bg: '#ffc107', text: '🔄 Connecting...', display: 'block' },
            disconnected: { bg: '#dc3545', text: '❌ Disconnected', display: 'block' },
            error: { bg: '#dc3545', text: `❌ ${message}`, display: 'block' },
            reconnecting: { bg: '#ffc107', text: '🔄 Reconnecting...', display: 'block' }
        };

        const config = states[state] || states.disconnected;
        indicator.style.backgroundColor = config.bg;
        indicator.style.color = 'white';
        indicator.textContent = message || config.text;
        indicator.style.display = config.display;
    }

    /**
     * Setup WebSocket event handlers
     */
    setupWebSocketHandlers() {
        const ws = window.optimizerWS;

        // Connection events
        ws.on('connection_changed', (data) => {
            console.log('🔌 Connection state changed:', data.state);
            this.updateConnectionIndicator(data.state);
        });

        ws.on('connection_error', (data) => {
            console.error('❌ Connection error:', data);
            this.updateConnectionIndicator('error', `Connection error (attempt ${data.attempts})`);
        });

        ws.on('reconnect_attempt', (data) => {
            console.log('🔄 Reconnection attempt:', data.attempt);
            this.updateConnectionIndicator('reconnecting', `Reconnecting (attempt ${data.attempt})`);
        });

        ws.on('reconnected', (data) => {
            console.log('✅ Reconnected after', data.attempts, 'attempts');
            if (typeof window.showAlert === 'function') {
                window.showAlert(`Reconnected successfully after ${data.attempts} attempts`, 'success');
            }
            this.updateConnectionIndicator('connected');
        });

        ws.on('connection_timeout', (data) => {
            console.warn('⚠️ Connection timeout detected', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Connection timeout detected, attempting to reconnect...', 'warning');
            }
        });

        ws.on('connection_failed', (data) => {
            console.error('❌ Connection failed:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Connection failed: ' + data.message, 'danger');
            }
            this.updateConnectionIndicator('disconnected', 'Connection Failed');
        });

        // Heartbeat events
        ws.on('optimization_heartbeat', (state) => {
            console.log('💓 Optimization heartbeat:', state);
            // Update progress indicator from heartbeat
            if (state.current_generation && state.total_generations) {
                // FIX: Pass object with current_generation and total_generations, not percentage
                const progress = {
                    current_generation: state.current_generation,
                    total_generations: state.total_generations
                };
                if (typeof window.updateProgressBar === 'function') {
                    window.updateProgressBar(progress);
                }
            }
        });

        // State recovery events
        ws.on('state_recovered', (state) => {
            console.log('🔄 State recovered:', state);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Connection restored. Optimization state recovered.', 'success');
            }

            if (state.running) {
                this.optimizationRunning = true;
                this.updateButtonStates('running', state.paused);

                // Update progress
                if (state.current_generation && state.total_generations) {
                    // FIX: Pass object with current_generation and total_generations, not percentage
                    const progress = {
                        current_generation: state.current_generation,
                        total_generations: state.total_generations
                    };
                    if (typeof window.updateProgressBar === 'function') {
                        window.updateProgressBar(progress);
                    }
                }
            }
        });

        // Optimization events
        ws.on('optimization_started', (data) => {
            console.log('🚀 Optimization started:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Optimization started successfully!', 'success');
            }
            this.optimizationRunning = true;
            this.updateButtonStates('running', false);

            // Initialize charts before showing them
            if (typeof window.showCharts === 'function') {
                console.log('📊 Calling showCharts() to initialize charts');
                window.showCharts();
            } else if (typeof window.initializeCharts === 'function') {
                console.log('📊 Calling initializeCharts() directly');
                document.getElementById('chartsSection').style.display = 'block';
                window.initializeCharts();
            } else {
                console.warn('⚠️ No chart initialization function available, just showing section');
                document.getElementById('chartsSection').style.display = 'block';
            }
        });

        ws.on('generation_complete', (data) => {
            console.log('📊 Generation complete:', data.generation);

            // Measure performance
            window.perfMonitor?.measure('generation_complete_handler', () => {
                // Update progress bar
                if (typeof window.updateProgressBar === 'function' && data.progress) {
                    window.updateProgressBar(data.progress);
                }

                // Schedule chart updates via optimized manager
                const chartData = data.optimizer_charts || data.chart_data || {};
                if (window.chartUpdateManager && Object.keys(chartData).length > 0) {
                    // Schedule debounced batch updates for each chart type
                    if (chartData.objective_evolution) {
                        window.chartUpdateManager.scheduleUpdate('objective', chartData);
                    }
                    if (chartData.elite_population_data) {
                        window.chartUpdateManager.scheduleUpdate('parallelCoords', chartData);
                    }
                    if (chartData.winning_trades_distribution) {
                        window.chartUpdateManager.scheduleUpdate('winningTrades', chartData.winning_trades_distribution);
                    }
                    if (chartData.losing_trades_distribution) {
                        window.chartUpdateManager.scheduleUpdate('losingTrades', chartData.losing_trades_distribution);
                    }
                    if (chartData.best_strategy) {
                        window.chartUpdateManager.scheduleUpdate('bestStrategy', chartData);
                    }
                } else if (typeof window.updateCharts === 'function') {
                    // Fallback to legacy update method
                    console.warn('⚠️ Using legacy updateCharts - chart update manager not available');
                    window.updateCharts(chartData);
                }

                // FIX: Update Performance Metrics Table (MUST be outside chart manager conditional)
                // This needs to run regardless of chart manager availability
                console.log('🔍 DEBUG: Performance Metrics Check:', {
                    hasPerformanceMetrics: !!chartData.performance_metrics,
                    performanceMetricsData: chartData.performance_metrics,
                    functionExists: typeof window.updatePerformanceMetricsTable === 'function',
                    tableColumnsData: chartData.table_columns
                });

                if (chartData.performance_metrics && typeof window.updatePerformanceMetricsTable === 'function') {
                    console.log('✅ Calling updatePerformanceMetricsTable with:', chartData.performance_metrics);
                    try {
                        window.updatePerformanceMetricsTable(chartData.performance_metrics, chartData.table_columns);
                        console.log('✅ updatePerformanceMetricsTable completed successfully');
                    } catch (error) {
                        console.error('❌ Error in updatePerformanceMetricsTable:', error);
                    }
                } else {
                    console.warn('⚠️ Performance metrics table NOT updated. Reason:', {
                        noData: !chartData.performance_metrics,
                        noFunction: typeof window.updatePerformanceMetricsTable !== 'function'
                    });
                }

                // FIX: Auto-update Parameter charts if a parameter is selected
                // This also needs to run regardless of chart manager availability
                const parameterSelector = document.getElementById('parameterSelector');
                const selectedParameter = parameterSelector ? parameterSelector.value : null;
                if (selectedParameter) {
                    console.log(`🔄 Auto-updating parameter charts for selected parameter: ${selectedParameter}`);
                    if (typeof window.loadParameterHistogram === 'function') {
                        window.loadParameterHistogram(selectedParameter);
                    }
                    if (typeof window.loadParameterEvolution === 'function') {
                        window.loadParameterEvolution(selectedParameter);
                    }
                }

                // Update parameter selector
                if (data.parameter_list && data.parameter_list.length > 0 && typeof window.updateParameterSelector === 'function') {
                    window.updateParameterSelector(data.parameter_list);
                }

                // Update test evaluations
                if (data.test_evaluations && data.test_evaluations.length > 0 && typeof window.updateTestEvaluations === 'function') {
                    window.updateTestEvaluations(data.test_evaluations);
                }
            });

            // Check frame rate
            window.perfMonitor?.checkFrameRate();
        });

        ws.on('optimization_complete', (data) => {
            console.log('✅ Optimization complete:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Optimization completed!', 'success');
            }
            this.optimizationRunning = false;
            this.updateButtonStates('complete', false);
        });

        ws.on('optimization_error', (data) => {
            console.error('❌ Optimization error:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert(`Optimization error: ${data.error}`, 'danger');
            }
            this.optimizationRunning = false;
            this.updateButtonStates('idle', false);
        });

        ws.on('optimization_paused', (data) => {
            console.log('⏸️ Optimization paused:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Optimization paused', 'info');
            }
            this.updateButtonStates('running', true);
        });

        ws.on('optimization_resumed', (data) => {
            console.log('▶️ Optimization resumed:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Optimization resumed', 'info');
            }
            this.updateButtonStates('running', false);
        });

        ws.on('optimization_stopping', (data) => {
            console.log('⏳ Optimization stopping:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Optimization is being stopped...', 'info');
            }
            // Don't change button states yet - wait for full stop
        });

        ws.on('optimization_stopped', (data) => {
            console.log('⏹️ Optimization stopped:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert('Optimization fully stopped', 'warning');
            }
            this.optimizationRunning = false;
            this.updateButtonStates('complete', false);
        });

        // Save events
        ws.on('save_current_success', (data) => {
            console.log('💾 Save successful:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert(`Saved current best at generation ${data.generation}`, 'success');
            }
        });

        ws.on('save_current_error', (data) => {
            console.error('❌ Save error:', data);
            if (typeof window.showAlert === 'function') {
                window.showAlert(`Save error: ${data.error}`, 'danger');
            }
        });
    }

    /**
     * Setup button event handlers
     */
    setupButtonHandlers() {
        const startBtn = document.getElementById('startOptimizerBtn');
        const pauseBtn = document.getElementById('pauseOptimizerBtn');
        const stopBtn = document.getElementById('stopOptimizerBtn');
        const saveBtn = document.getElementById('saveOptimizedConfigsBtn');

        startBtn.addEventListener('click', () => this.handleStartOptimization());
        pauseBtn.addEventListener('click', () => this.handlePauseResume());
        stopBtn.addEventListener('click', () => this.handleStopOptimization());
    }

    /**
     * Handle start optimization button
     */
    async handleStartOptimization() {
        if (!window.currentConfigs || !window.currentConfigs.ga_config || !window.currentConfigs.data_config) {
            if (typeof window.showAlert === 'function') {
                window.showAlert('Please load both GA and data configurations first', 'warning');
            }
            return;
        }

        // Check connection state
        const connState = window.optimizerWS.getConnectionState();
        if (!connState.connected) {
            if (typeof window.showAlert === 'function') {
                window.showAlert('WebSocket not connected. Please wait for connection.', 'warning');
            }
            return;
        }

        try {
            this.updateButtonStates('starting', false);
            this.hideEliteButtons();
            this.clearAllChartsAndData();

            // Collect current configs from UI
            const updatedGAConfig = collectAllConfigs();
            collectDataConfigData();
            collectTestDataConfigData();

            const response = await fetch('/optimizer/api/start_optimization', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ga_config: updatedGAConfig,
                    data_config: dataConfig,
                    test_data_config: testDataConfig
                })
            });

            const result = await response.json();

            if (result.success) {
                this.optimizationRunning = true;
                if (typeof window.showAlert === 'function') {
                    window.showAlert('Configurations prepared, starting optimization...', 'info');
                }

                // Send start signal via WebSocket
                window.optimizerWS.startOptimization({
                    ga_config_path: result.ga_config_path,
                    data_config_path: result.data_config_path,
                    test_data_config_path: result.test_data_config_path
                });
            } else {
                if (typeof window.showAlert === 'function') {
                    window.showAlert(`Failed to prepare optimization: ${result.error}`, 'danger');
                }
                this.updateButtonStates('idle', false);
            }
        } catch (error) {
            console.error('❌ Error starting optimization:', error);
            if (typeof window.showAlert === 'function') {
                window.showAlert(`Error: ${error.message}`, 'danger');
            }
            this.updateButtonStates('idle', false);
        }
    }

    /**
     * Handle pause/resume button
     */
    handlePauseResume() {
        const pauseBtn = document.getElementById('pauseOptimizerBtn');
        const isPaused = pauseBtn.innerHTML.includes('Resume');

        if (isPaused) {
            window.optimizerWS.resumeOptimization();
        } else {
            window.optimizerWS.pauseOptimization();
        }
    }

    /**
     * Handle stop optimization button
     */
    handleStopOptimization() {
        if (confirm('Are you sure you want to stop the optimization?')) {
            window.optimizerWS.stopOptimization();
        }
    }

    /**
     * Update button states based on optimization state
     */
    updateButtonStates(state, paused) {
        const startBtn = document.getElementById('startOptimizerBtn');
        const pauseBtn = document.getElementById('pauseOptimizerBtn');
        const stopBtn = document.getElementById('stopOptimizerBtn');
        const saveBtn = document.getElementById('saveOptimizedConfigsBtn');
        const loadEliteBtn = document.getElementById('loadEliteToFormsBtn');
        const sendToReplayBtn = document.getElementById('sendToReplayBtn');

        switch (state) {
            case 'idle':
                startBtn.disabled = false;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                break;

            case 'starting':
                startBtn.disabled = true;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                break;

            case 'running':
                startBtn.disabled = true;
                pauseBtn.disabled = false;
                stopBtn.disabled = false;

                if (paused) {
                    pauseBtn.innerHTML = '<i class="fas fa-play me-2"></i>Resume';
                    pauseBtn.className = 'btn btn-success btn-lg me-3';
                } else {
                    pauseBtn.innerHTML = '<i class="fas fa-pause me-2"></i>Pause';
                    pauseBtn.className = 'btn btn-warning btn-lg me-3';
                }
                break;

            case 'complete':
                startBtn.disabled = false;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                saveBtn.style.display = 'inline-block';
                saveBtn.disabled = false;
                loadEliteBtn.style.display = 'inline-block';
                loadEliteBtn.disabled = false;
                sendToReplayBtn.style.display = 'inline-block';
                sendToReplayBtn.disabled = false;
                break;
        }
    }

    /**
     * Hide elite-related buttons
     */
    hideEliteButtons() {
        const saveBtn = document.getElementById('saveOptimizedConfigsBtn');
        const loadEliteBtn = document.getElementById('loadEliteToFormsBtn');
        const sendToReplayBtn = document.getElementById('sendToReplayBtn');

        if (saveBtn) saveBtn.style.display = 'none';
        if (loadEliteBtn) loadEliteBtn.style.display = 'none';
        if (sendToReplayBtn) sendToReplayBtn.style.display = 'none';
    }

    /**
     * Clear all charts and data
     */
    clearAllChartsAndData() {
        this.addedGenerations.clear();

        // Also clear the global addedGenerations set from main.html
        // This is used by updatePerformanceMetricsTable to track which generations have been added
        if (window.addedGenerations && typeof window.addedGenerations.clear === 'function') {
            window.addedGenerations.clear();
            console.log('🧹 Cleared global addedGenerations set');
        }

        // Clear charts if they exist
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.destroy) {
                chart.destroy();
            }
        });
        this.charts = {};

        // Clear test evaluations table
        const testEvalsTable = document.getElementById('testEvaluationsTable');
        if (testEvalsTable) {
            testEvalsTable.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No test evaluation data yet</td></tr>';
        }

        // Clear performance metrics table
        const metricsTable = document.getElementById('metricsTable');
        if (metricsTable) {
            metricsTable.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No performance data yet</td></tr>';
        }

        console.log('🧹 Cleared all charts and data');
    }
}

// Create global instance
window.optimizerUI = new OptimizerUIIntegration();

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.optimizerUI.init();
});
