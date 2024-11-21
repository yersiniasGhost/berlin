import asyncio
import websockets
import json


async def send_message(uri, identifier):
    async with websockets.connect(uri) as websocket:
        # Example subscription message to ActionCable
        subscription_message = {
            "command": "subscribe",
            "identifier": json.dumps({
                "channel": "BacktestChannel",
                "identifier": identifier
            })
        }

        # Send subscription message
        await websocket.send(json.dumps(subscription_message))

        # Keep listening for messages
        while True:
            # Send message to Rails ActionCable
            message_data = {
                "command": "message",
                "identifier": json.dumps({
                    "channel": "BacktestChannel",
                    "identifier": identifier
                }),
                "data": json.dumps({
                    "action": "receive_message",
                    "some_data": "data from python backend"
                })
            }

            await websocket.send(json.dumps(message_data))
            print(f"Sent message: {message_data}")

            # Receive and print messages from Rails
            response = await websocket.recv()
            print(f"Received from Rails: {response}")

            await asyncio.sleep(5)  # Send a message every 2 seconds (or your logic)


# Run the client to connect to the Rails WebSocket
identifier = "your_unique_identifier"
uri = "ws://localhost:3000/cable"  # Replace with your Rails ActionCable URL
asyncio.get_event_loop().run_until_complete(send_message(uri, identifier))
