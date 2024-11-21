import asyncio
import websockets
import json
from threading import Thread


class WebSocketClient:
    def __init__(self, uri: str, identifier: str):
        self.uri = uri
        self.identifier = identifier
        self.websocket = None
        self.channel = "BacktestChannel"
        self.channel_identifier = json.dumps({
            "channel": self.channel,
            "identifier": self.identifier
        })
        self.loop = None
        self.running = False
        self._start_background_loop()



    def _start_background_loop(self):
        """Start a background thread with an event loop for async operations"""

        def run_event_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        thread = Thread(target=run_event_loop, daemon=True)
        thread.start()


    async def connect(self):
        if not self.websocket or not self.websocket.open:
            self.websocket = await websockets.connect(self.uri)
            await self.websocket.send(json.dumps({
                "command": "subscribe",
                "identifier": self.channel_identifier
            }))
            self.running = True



    async def ensure_connection(self):
        """Ensure the WebSocket connection is established"""
        if not self.websocket or not self.websocket.open:
            await self.connect()



    async def _send_data(self, data):
        await self.ensure_connection()
        message = json.dumps({
            "command": "message",
            "identifier": self.channel_identifier,
            "data": json.dumps({
                "action": "receive_data",
                "data": data
            })
        })
        await self.websocket.send(message)



    def send_data(self, data):
        """Synchronous method to send data"""
        if self.loop is None:
            raise RuntimeError("Background event loop not started")

        future = asyncio.run_coroutine_threadsafe(
            self._send_data(data),
            self.loop
        )
        # Wait for the result with a timeout
        try:
            future.result(timeout=5)
        except Exception as e:
            print(f"Error sending data: {e}")



    def close(self):
        """Cleanup method to close the connection"""
        if self.loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._cleanup(),
                self.loop
            )


    async def _cleanup(self):
        """Async cleanup method"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
        if self.loop:
            self.loop.stop()