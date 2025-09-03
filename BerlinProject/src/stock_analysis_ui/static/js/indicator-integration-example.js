/**
 * Example integration of IndicatorChartComponent for Stock Analysis UI
 * 
 * This file demonstrates how to integrate the reusable indicator chart component
 * into the stock analysis UI for displaying MACD, SMA, and other indicators
 * with dynamic checkboxes and trigger graphs.
 */

class StockAnalysisIndicatorManager {
    constructor() {
        this.indicatorComponent = null;
        this.currentCardData = null;
        this.socket = null;
        
        this.init();
    }
    
    init() {
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initialize());
        } else {
            this.initialize();
        }
    }
    
    initialize() {
        // Initialize the indicator chart component
        this.initializeIndicatorComponent();
        
        // Set up WebSocket connection for real-time updates
        this.initializeWebSocket();
        
        // Set up card data loading
        this.setupCardDataLoading();
    }
    
    /**
     * Initialize the indicator chart component
     */
    initializeIndicatorComponent() {
        // Look for a container in the card details page
        const container = document.getElementById('indicatorChartsContainer') || 
                         document.getElementById('chartContainer') ||
                         this.createIndicatorContainer();
        
        if (!container) {
            console.warn('No suitable container found for indicator charts');
            return;
        }
        
        this.indicatorComponent = new IndicatorChartComponent(container.id, {
            showTriggerGraphs: true,
            chartHeight: 400,
            indicatorHeight: 180,
            triggerHeight: 80
        });
    }
    
    /**
     * Create indicator container if it doesn't exist
     */
    createIndicatorContainer() {
        // Find a suitable place to insert the indicator container
        const chartSection = document.querySelector('.chart-section') ||
                            document.querySelector('#candlestick-chart')?.parentElement ||
                            document.querySelector('.main-content');
                            
        if (!chartSection) return null;
        
        // Create indicator container
        const container = document.createElement('div');
        container.id = 'indicatorChartsContainer';
        container.className = 'indicator-charts-section mt-4';
        
        // Insert after existing chart or at the end of chart section
        const existingChart = document.querySelector('#candlestick-chart');
        if (existingChart) {
            existingChart.parentElement.insertBefore(container, existingChart.nextSibling);
        } else {
            chartSection.appendChild(container);
        }
        
        return container;
    }
    
    /**
     * Initialize WebSocket connection for real-time updates
     */
    initializeWebSocket() {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not available, real-time updates disabled');
            return;
        }
        
        this.socket = io();
        
        // Listen for card updates
        this.socket.on('card_update', (data) => {
            this.handleCardUpdate(data);
        });
        
        // Listen for candle completed events
        this.socket.on('candle_completed', (data) => {
            this.handleCandleCompleted(data);
        });
    }
    
    /**
     * Set up card data loading from API
     */
    setupCardDataLoading() {
        // Get card ID from URL or data attributes
        const cardId = this.getCardId();
        if (cardId) {
            this.loadCardData(cardId);
        }
    }
    
    /**
     * Get card ID from current context
     */
    getCardId() {
        // Try multiple methods to get card ID
        const urlParams = new URLSearchParams(window.location.search);
        let cardId = urlParams.get('card_id') || urlParams.get('cardId');
        
        if (!cardId) {
            const pathParts = window.location.pathname.split('/');
            const cardIndex = pathParts.indexOf('card');
            if (cardIndex !== -1 && cardIndex + 1 < pathParts.length) {
                cardId = pathParts[cardIndex + 1];
            }
        }
        
        if (!cardId) {
            const cardElement = document.querySelector('[data-card-id]');
            if (cardElement) {
                cardId = cardElement.dataset.cardId;
            }
        }
        
        return cardId;
    }
    
    /**
     * Load card data from API
     */
    async loadCardData(cardId) {
        try {
            // Fetch monitor configuration for this card
            const configResponse = await fetch(`/api/combinations/${cardId}/config`);
            if (!configResponse.ok) throw new Error('Failed to fetch config');
            
            const configData = await configResponse.json();
            
            // Load indicators into component
            if (this.indicatorComponent && configData.monitor_config) {
                this.indicatorComponent.loadIndicators(configData.monitor_config);
            }
            
            // Fetch historical chart data
            const chartResponse = await fetch(`/api/combinations/${cardId}/chart_data`);
            if (!chartResponse.ok) throw new Error('Failed to fetch chart data');
            
            const chartData = await chartResponse.json();
            
            // Set chart data in component
            if (this.indicatorComponent) {
                this.indicatorComponent.setChartData(chartData);
            }
            
            this.currentCardData = { cardId, config: configData, chartData };
            
        } catch (error) {
            console.error('Error loading card data:', error);
        }
    }
    
    /**
     * Handle real-time card updates from WebSocket
     */
    handleCardUpdate(data) {
        if (!this.indicatorComponent || !this.currentCardData) return;
        
        // Check if this update is for our current card
        if (data.card_id !== this.currentCardData.cardId) return;
        
        // Extract indicator values and create trigger data
        const indicators = data.indicators || {};
        const triggerData = this.processTriggerData(data);
        
        // Update the indicator component
        this.indicatorComponent.updateIndicatorData(indicators, triggerData);
    }
    
    /**
     * Handle completed candle events
     */
    handleCandleCompleted(data) {
        if (!this.indicatorComponent || !this.currentCardData) return;
        
        // Check if this update is for our current card
        if (data.card_id !== this.currentCardData.cardId) return;
        
        // Add new candle to chart data
        if (data.completed_candle) {
            // Update the main chart with new candle
            // This would typically trigger a chart update
            console.log('New candle completed:', data.completed_candle);
        }
    }
    
    /**
     * Process raw data into trigger data format (0-1 values)
     */
    processTriggerData(data) {
        const triggerData = {};
        
        // Process bar scores as trigger signals
        if (data.bar_scores) {
            Object.entries(data.bar_scores).forEach(([barName, score]) => {
                // Convert bar score to 0-1 trigger signal
                triggerData[barName] = Math.abs(score) > 0.5 ? 1 : 0;
            });
        }
        
        // Process raw indicators for specific patterns
        if (data.raw_indicators) {
            Object.entries(data.raw_indicators).forEach(([indicatorName, value]) => {
                // Create trigger based on indicator threshold
                // This is simplified - you'd use actual indicator logic
                if (indicatorName.toLowerCase().includes('macd')) {
                    triggerData[indicatorName] = value > 0 ? 1 : 0;
                } else if (indicatorName.toLowerCase().includes('sma')) {
                    // For SMA, could compare price vs SMA
                    triggerData[indicatorName] = data.price > value ? 1 : 0;
                } else {
                    // Default threshold logic
                    triggerData[indicatorName] = Math.abs(value) > 0.1 ? 1 : 0;
                }
            });
        }
        
        return triggerData;
    }
    
    /**
     * Public method to manually refresh data
     */
    refresh() {
        const cardId = this.getCardId();
        if (cardId) {
            this.loadCardData(cardId);
        }
    }
    
    /**
     * Public method to destroy the component
     */
    destroy() {
        if (this.indicatorComponent) {
            this.indicatorComponent.destroy();
        }
        
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// Auto-initialize when loaded
let stockAnalysisIndicatorManager = null;

// Initialize on page load
(function() {
    function initialize() {
        stockAnalysisIndicatorManager = new StockAnalysisIndicatorManager();
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
})();

// Export for manual control if needed
if (typeof window !== 'undefined') {
    window.StockAnalysisIndicatorManager = StockAnalysisIndicatorManager;
    window.stockAnalysisIndicatorManager = stockAnalysisIndicatorManager;
}