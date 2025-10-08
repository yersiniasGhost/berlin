/**
 * Persistent Candle History Manager
 * Manages candle history storage and retrieval across page navigation
 */

class CandleHistoryManager {
    constructor() {
        this.maxCandlesPerTimeframe = 100;
        this.storagePrefix = 'candle_history_';
    }

    /**
     * Get storage key for a specific card and timeframe
     */
    getStorageKey(cardId, timeframe) {
        return `${this.storagePrefix}${cardId}_${timeframe}`;
    }

    /**
     * Store a completed candle
     */
    storeCompletedCandle(cardId, timeframe, candleData) {
        try {
            const storageKey = this.getStorageKey(cardId, timeframe);
            
            // Get existing history
            let history = this.getCandleHistory(cardId, timeframe);
            
            // Convert candleData to consistent format and ensure valid timestamp
            let timestamp = candleData.timestamp || candleData[0];
            
            // Convert timestamp to number if it's not already
            if (typeof timestamp === 'string') {
                timestamp = new Date(timestamp).getTime();
            } else if (timestamp instanceof Date) {
                timestamp = timestamp.getTime();
            }
            
            // Validate timestamp - reject if it's invalid or too old/future
            const now = Date.now();
            const oneWeekAgo = now - (7 * 24 * 60 * 60 * 1000);
            const oneHourFuture = now + (60 * 60 * 1000);
            
            if (!timestamp || timestamp < oneWeekAgo || timestamp > oneHourFuture) {
                console.warn(`Invalid timestamp for candle, rejecting:`, timestamp, new Date(timestamp));
                return false;
            }
            
            const candle = {
                timestamp: timestamp,
                open: parseFloat(candleData.open || candleData[1]),
                high: parseFloat(candleData.high || candleData[2]),
                low: parseFloat(candleData.low || candleData[3]),
                close: parseFloat(candleData.close || candleData[4]),
                storedAt: now
            };

            // Check if this candle already exists (avoid duplicates)
            const existingIndex = history.findIndex(existing => 
                Math.abs(existing.timestamp - candle.timestamp) < 60000 // Within 1 minute
            );
            
            if (existingIndex !== -1) {
                console.log(`Candle already exists for ${new Date(timestamp).toLocaleTimeString()}, skipping duplicate`);
                return false;
            }

            // Add to history
            history.push(candle);
            
            // Sort by timestamp (newest first)
            history.sort((a, b) => b.timestamp - a.timestamp);

            // Limit to max candles
            if (history.length > this.maxCandlesPerTimeframe) {
                history = history.slice(0, this.maxCandlesPerTimeframe);
            }

            // Store back to localStorage
            localStorage.setItem(storageKey, JSON.stringify(history));
            
            console.log(`Stored candle for ${cardId} ${timeframe}:`, new Date(candle.timestamp).toLocaleTimeString(), candle);
            return true;

        } catch (error) {
            console.error('Error storing completed candle:', error);
            return false;
        }
    }

    /**
     * Get candle history for a specific card and timeframe
     */
    getCandleHistory(cardId, timeframe) {
        try {
            const storageKey = this.getStorageKey(cardId, timeframe);
            const stored = localStorage.getItem(storageKey);
            
            if (!stored) {
                return [];
            }

            const history = JSON.parse(stored);
            
            // Validate and clean up data
            const now = Date.now();
            const threeDaysAgo = now - (3 * 24 * 60 * 60 * 1000); // Keep candles for 3 days instead of 1
            const oneWeekAgo = now - (7 * 24 * 60 * 60 * 1000);
            const oneHourFuture = now + (60 * 60 * 1000);
            
            const filtered = history.filter(candle => {
                // Remove if missing required fields
                if (!candle.timestamp || !candle.open || !candle.high || !candle.low || !candle.close) {
                    return false;
                }
                
                // Remove if stored too long ago (3 days instead of 1)
                if (candle.storedAt && candle.storedAt < threeDaysAgo) {
                    return false;
                }
                
                // Remove if timestamp is invalid (too old or too future)
                if (candle.timestamp < oneWeekAgo || candle.timestamp > oneHourFuture) {
                    console.warn(`Removing invalid timestamp candle:`, new Date(candle.timestamp));
                    return false;
                }
                
                return true;
            });

            // Sort by timestamp (newest first)
            filtered.sort((a, b) => b.timestamp - a.timestamp);

            // If we filtered anything, save the cleaned history
            if (filtered.length !== history.length) {
                localStorage.setItem(storageKey, JSON.stringify(filtered));
            }

            return filtered;

        } catch (error) {
            console.error('Error getting candle history:', error);
            return [];
        }
    }

    /**
     * Clear all candle history for a specific card
     */
    clearCardHistory(cardId) {
        try {
            const keys = Object.keys(localStorage);
            const cardKeys = keys.filter(key => 
                key.startsWith(`${this.storagePrefix}${cardId}_`)
            );

            cardKeys.forEach(key => localStorage.removeItem(key));
            
            console.log(`Cleared candle history for card ${cardId}`);
            return true;

        } catch (error) {
            console.error('Error clearing card history:', error);
            return false;
        }
    }

    /**
     * Get all cards that have stored history
     */
    getStoredCards() {
        try {
            const keys = Object.keys(localStorage);
            const historyKeys = keys.filter(key => key.startsWith(this.storagePrefix));
            
            const cards = new Set();
            historyKeys.forEach(key => {
                const parts = key.replace(this.storagePrefix, '').split('_');
                if (parts.length >= 1) {
                    cards.add(parts[0]); // cardId is first part
                }
            });

            return Array.from(cards);

        } catch (error) {
            console.error('Error getting stored cards:', error);
            return [];
        }
    }

    /**
     * Get memory usage info
     */
    getStorageInfo() {
        try {
            const keys = Object.keys(localStorage);
            const historyKeys = keys.filter(key => key.startsWith(this.storagePrefix));
            
            let totalCandles = 0;
            let totalSize = 0;

            historyKeys.forEach(key => {
                const data = localStorage.getItem(key);
                if (data) {
                    totalSize += data.length;
                    try {
                        const parsed = JSON.parse(data);
                        totalCandles += parsed.length;
                    } catch (e) {
                        // Invalid data, remove it
                        localStorage.removeItem(key);
                    }
                }
            });

            return {
                keys: historyKeys.length,
                totalCandles,
                totalSizeBytes: totalSize,
                totalSizeKB: Math.round(totalSize / 1024)
            };

        } catch (error) {
            console.error('Error getting storage info:', error);
            return { keys: 0, totalCandles: 0, totalSizeBytes: 0, totalSizeKB: 0 };
        }
    }

    /**
     * Clean up old or invalid data
     */
    cleanup() {
        try {
            const keys = Object.keys(localStorage);
            const historyKeys = keys.filter(key => key.startsWith(this.storagePrefix));
            
            const threeDaysAgo = Date.now() - (3 * 24 * 60 * 60 * 1000);
            let cleanedKeys = 0;

            historyKeys.forEach(key => {
                try {
                    const data = localStorage.getItem(key);
                    if (!data) {
                        localStorage.removeItem(key);
                        cleanedKeys++;
                        return;
                    }

                    const history = JSON.parse(data);
                    if (!Array.isArray(history)) {
                        localStorage.removeItem(key);
                        cleanedKeys++;
                        return;
                    }

                    // Filter out old candles
                    const filtered = history.filter(candle => 
                        candle.storedAt && candle.storedAt > threeDaysAgo
                    );

                    if (filtered.length === 0) {
                        localStorage.removeItem(key);
                        cleanedKeys++;
                    } else if (filtered.length !== history.length) {
                        localStorage.setItem(key, JSON.stringify(filtered));
                    }

                } catch (e) {
                    localStorage.removeItem(key);
                    cleanedKeys++;
                }
            });

            console.log(`Cleaned up ${cleanedKeys} candle history keys`);
            return cleanedKeys;

        } catch (error) {
            console.error('Error during cleanup:', error);
            return 0;
        }
    }
    
    /**
     * Clear all candle history and start fresh session
     */
    clearAllHistory() {
        try {
            const keys = Object.keys(localStorage);
            const candleKeys = keys.filter(key => key.startsWith(this.storagePrefix));
            
            candleKeys.forEach(key => {
                localStorage.removeItem(key);
            });
            
            // Remove session tracking
            localStorage.removeItem('candle_session_id');
            
            console.log(`Cleared all ${candleKeys.length} candle history entries`);
            return candleKeys.length;
            
        } catch (error) {
            console.error('Error clearing all history:', error);
            return 0;
        }
    }

    /**
     * One-time cleanup of invalid candles (like timestamps from wrong time zones or bad data)
     */
    cleanupInvalidCandles() {
        try {
            const keys = Object.keys(localStorage);
            const historyKeys = keys.filter(key => key.startsWith(this.storagePrefix));
            
            let removedCandles = 0;
            const now = Date.now();
            const sixHoursAgo = now - (6 * 60 * 60 * 1000);
            const twoHoursFromNow = now + (2 * 60 * 60 * 1000);

            historyKeys.forEach(key => {
                try {
                    const data = localStorage.getItem(key);
                    if (!data) return;

                    const history = JSON.parse(data);
                    if (!Array.isArray(history)) return;

                    const before = history.length;
                    
                    // Filter out candles with suspicious timestamps
                    const filtered = history.filter(candle => {
                        if (!candle.timestamp) return false;
                        
                        const candleTime = new Date(candle.timestamp).getTime();
                        
                        // Remove candles that are way outside current time window
                        // This catches issues like the 12:59 PM candle when it should be 1:XX PM
                        if (candleTime < sixHoursAgo || candleTime > twoHoursFromNow) {
                            console.log(`Removing suspicious candle: ${new Date(candleTime).toLocaleTimeString()}`);
                            return false;
                        }
                        
                        return true;
                    });

                    removedCandles += (before - filtered.length);

                    if (filtered.length !== before) {
                        if (filtered.length === 0) {
                            localStorage.removeItem(key);
                        } else {
                            localStorage.setItem(key, JSON.stringify(filtered));
                        }
                    }

                } catch (e) {
                    console.error('Error cleaning candle history key:', key, e);
                }
            });

            if (removedCandles > 0) {
                console.log(`Removed ${removedCandles} invalid candles from history`);
            }
            
            return removedCandles;

        } catch (error) {
            console.error('Error during invalid candle cleanup:', error);
            return 0;
        }
    }
}

// Global instance
window.candleHistoryManager = new CandleHistoryManager();

// Run cleanup on page load
document.addEventListener('DOMContentLoaded', function() {
    window.candleHistoryManager.cleanup();
    
    // One-time cleanup of invalid candles (like the 12:59 PM issue)
    window.candleHistoryManager.cleanupInvalidCandles();
});

// Global WebSocket handler for candle_completed events
// This ensures candles are stored regardless of which page is active
function setupGlobalCandleHandler(socket) {
    socket.on('candle_completed', function(data) {
        console.log('Global candle handler received:', data);
        
        if (!data.card_id || !data.timeframe || !data.completed_candle) {
            console.warn('Invalid candle_completed data:', data);
            return;
        }

        // Store the completed candle
        const success = window.candleHistoryManager.storeCompletedCandle(
            data.card_id,
            data.timeframe,
            data.completed_candle
        );

        if (success) {
            // Trigger custom event for pages that want to update their UI
            const customEvent = new CustomEvent('candleHistoryUpdated', {
                detail: {
                    cardId: data.card_id,
                    timeframe: data.timeframe,
                    candleData: data.completed_candle
                }
            });
            document.dispatchEvent(customEvent);
        }
    });

    console.log('Global candle history handler initialized');
}

// Export for use in other scripts
window.setupGlobalCandleHandler = setupGlobalCandleHandler;