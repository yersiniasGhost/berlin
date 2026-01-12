/**
 * Optimizer WebSocket Connection Manager
 * Handles robust WebSocket communication with reconnection and heartbeat
 */

class OptimizerWebSocket {
    constructor() {
        this.socket = null;
        this.connectionState = 'disconnected'; // disconnected, connecting, connected
        this.heartbeatInterval = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 2000; // Start with 2 seconds
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.lastHeartbeat = null;
        this.heartbeatTimeout = 15000; // 15 seconds without heartbeat = problem
        this.heartbeatCheckInterval = null;
        this.optimizationRunning = false;
        this.eventHandlers = {};
    }

    /**
     * Initialize WebSocket connection with proper configuration
     */
    connect() {
        if (this.socket && this.connectionState === 'connected') {
            console.log('🔌 WebSocket already connected');
            return;
        }

        console.log('🔌 Initializing WebSocket connection...');
        this.connectionState = 'connecting';

        this.socket = io({
            // Reconnection settings
            reconnection: true,
            reconnectionAttempts: this.maxReconnectAttempts,
            reconnectionDelay: this.reconnectDelay,
            reconnectionDelayMax: this.maxReconnectDelay,
            randomizationFactor: 0.5,

            // Timeout settings
            timeout: 20000, // 20 seconds connection timeout

            // Transport settings
            transports: ['websocket', 'polling'], // Try WebSocket first, fallback to polling
            upgrade: true,

            // Ping/pong settings
            pingInterval: 25000, // Send ping every 25 seconds
            pingTimeout: 10000 // Wait 10 seconds for pong response
        });

        this.setupEventHandlers();
        this.startHeartbeatMonitoring();
    }

    /**
     * Setup all WebSocket event handlers
     */
    setupEventHandlers() {
        // Connection events
        this.socket.on('connect', () => {
            console.log('✅ WebSocket connected');
            this.connectionState = 'connected';
            this.reconnectAttempts = 0;
            this.reconnectDelay = 2000; // Reset reconnect delay
            this.lastHeartbeat = Date.now();
            this.emit('connection_changed', { state: 'connected' });

            // Request state recovery if optimization was running
            if (this.optimizationRunning) {
                console.log('🔄 Reconnected during optimization, requesting state recovery');
                this.socket.emit('request_state_recovery');
            }
        });

        this.socket.on('disconnect', (reason) => {
            console.warn('⚠️ WebSocket disconnected:', reason);
            this.connectionState = 'disconnected';
            this.emit('connection_changed', { state: 'disconnected', reason });

            if (reason === 'io server disconnect') {
                // Server initiated disconnect, reconnect manually
                console.log('🔄 Server disconnected, attempting manual reconnect...');
                setTimeout(() => this.socket.connect(), 1000);
            }
        });

        this.socket.on('connect_error', (error) => {
            console.error('❌ WebSocket connection error:', error);
            this.connectionState = 'disconnected';
            this.reconnectAttempts++;

            // Exponential backoff
            this.reconnectDelay = Math.min(
                this.reconnectDelay * 1.5,
                this.maxReconnectDelay
            );

            this.emit('connection_error', { error, attempts: this.reconnectAttempts });

            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                console.error('❌ Max reconnection attempts reached');
                this.emit('connection_failed', {
                    message: 'Failed to reconnect after multiple attempts'
                });
            }
        });

        this.socket.on('reconnect', (attemptNumber) => {
            console.log(`✅ Reconnected after ${attemptNumber} attempts`);
            this.emit('reconnected', { attempts: attemptNumber });
        });

        this.socket.on('reconnect_attempt', (attemptNumber) => {
            console.log(`🔄 Reconnection attempt ${attemptNumber}...`);
            this.emit('reconnect_attempt', { attempt: attemptNumber });
        });

        // Heartbeat events
        this.socket.on('heartbeat', (data) => {
            this.lastHeartbeat = Date.now();
            console.log('💓 Heartbeat received:', data);

            // Update optimization state from heartbeat
            if (data.optimization_state) {
                this.emit('optimization_heartbeat', data.optimization_state);
            }
        });

        // Optimization state recovery
        this.socket.on('state_recovery', (data) => {
            console.log('🔄 State recovery received:', data);
            this.emit('state_recovered', data);
        });

        // Optimization events
        this.socket.on('optimization_started', (data) => {
            console.log('🚀 Optimization started:', data);
            this.optimizationRunning = true;
            this.emit('optimization_started', data);
        });

        this.socket.on('generation_complete', (data) => {
            console.log(`📊 Generation ${data.generation} complete`);
            this.lastHeartbeat = Date.now(); // Treat generation updates as heartbeat
            this.emit('generation_complete', data);
        });

        this.socket.on('optimization_complete', (data) => {
            console.log('✅ Optimization complete:', data);
            this.optimizationRunning = false;
            this.emit('optimization_complete', data);
        });

        this.socket.on('optimization_error', (data) => {
            console.error('❌ Optimization error:', data);
            this.optimizationRunning = false;
            this.emit('optimization_error', data);
        });

        this.socket.on('optimization_paused', (data) => {
            console.log('⏸️ Optimization paused:', data);
            this.emit('optimization_paused', data);
        });

        this.socket.on('optimization_resumed', (data) => {
            console.log('▶️ Optimization resumed:', data);
            this.emit('optimization_resumed', data);
        });

        this.socket.on('optimization_stopping', (data) => {
            console.log('⏳ Optimization stopping:', data);
            this.emit('optimization_stopping', data);
        });

        this.socket.on('optimization_stopped', (data) => {
            console.log('⏹️ Optimization stopped:', data);
            this.optimizationRunning = false;
            this.emit('optimization_stopped', data);
        });

        // Save events
        this.socket.on('save_current_success', (data) => {
            console.log('💾 Save successful:', data);
            this.emit('save_current_success', data);
        });

        this.socket.on('save_current_error', (data) => {
            console.error('❌ Save error:', data);
            this.emit('save_current_error', data);
        });
    }

    /**
     * Start monitoring heartbeat to detect dead connections
     */
    startHeartbeatMonitoring() {
        // Clear existing interval
        if (this.heartbeatCheckInterval) {
            clearInterval(this.heartbeatCheckInterval);
        }

        // Check heartbeat every 5 seconds
        this.heartbeatCheckInterval = setInterval(() => {
            if (this.connectionState !== 'connected') {
                return;
            }

            const timeSinceLastHeartbeat = Date.now() - (this.lastHeartbeat || 0);

            if (timeSinceLastHeartbeat > this.heartbeatTimeout) {
                console.warn(`⚠️ No heartbeat for ${timeSinceLastHeartbeat}ms, connection may be dead`);

                if (this.optimizationRunning) {
                    console.warn('⚠️ Optimization running with dead connection!');
                    this.emit('connection_timeout', {
                        timeSinceHeartbeat: timeSinceLastHeartbeat,
                        optimizationRunning: this.optimizationRunning
                    });

                    // Try to reconnect
                    this.socket.disconnect();
                    this.socket.connect();
                }
            }
        }, 5000);
    }

    /**
     * Register event handler
     */
    on(event, handler) {
        if (!this.eventHandlers[event]) {
            this.eventHandlers[event] = [];
        }
        this.eventHandlers[event].push(handler);
    }

    /**
     * Emit event to registered handlers
     */
    emit(event, data) {
        const handlers = this.eventHandlers[event] || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`Error in ${event} handler:`, error);
            }
        });
    }

    /**
     * Send event to server
     */
    send(event, data) {
        if (!this.socket || this.connectionState !== 'connected') {
            console.error(`❌ Cannot send ${event}: not connected`);
            this.emit('send_failed', { event, data, reason: 'Not connected' });
            return false;
        }

        console.log(`📤 Sending ${event}:`, data);
        this.socket.emit(event, data);
        return true;
    }

    /**
     * Start optimization
     */
    startOptimization(data) {
        if (this.send('start_optimization', data)) {
            this.optimizationRunning = true;
            return true;
        }
        return false;
    }

    /**
     * Pause optimization
     */
    pauseOptimization() {
        return this.send('pause_optimization', {});
    }

    /**
     * Resume optimization
     */
    resumeOptimization() {
        return this.send('resume_optimization', {});
    }

    /**
     * Stop optimization
     */
    stopOptimization() {
        if (this.send('stop_optimization', {})) {
            this.optimizationRunning = false;
            return true;
        }
        return false;
    }

    /**
     * Save current best
     */
    saveCurrentBest() {
        return this.send('save_current_best', {});
    }

    /**
     * Get connection state
     */
    getConnectionState() {
        return {
            state: this.connectionState,
            connected: this.connectionState === 'connected',
            optimizationRunning: this.optimizationRunning,
            lastHeartbeat: this.lastHeartbeat,
            timeSinceHeartbeat: this.lastHeartbeat ? Date.now() - this.lastHeartbeat : null
        };
    }

    /**
     * Cleanup and disconnect
     */
    disconnect() {
        console.log('🔌 Disconnecting WebSocket...');

        if (this.heartbeatCheckInterval) {
            clearInterval(this.heartbeatCheckInterval);
        }

        if (this.socket) {
            this.socket.disconnect();
        }

        this.connectionState = 'disconnected';
        this.optimizationRunning = false;
    }
}

// Create global instance
window.optimizerWS = new OptimizerWebSocket();
