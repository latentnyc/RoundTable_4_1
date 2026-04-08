import asyncio
import socketio

sio = socketio.AsyncClient(logger=True, engineio_logger=True)

@sio.event
async def connect():
    print('connection established')

@sio.event
async def connect_error(e):
    print("The connection failed!")
    print(e)

@sio.event
async def disconnect():
    print('disconnected from server')

async def main():
    try:
        await sio.connect('http://localhost:8000', auth={'token': 'test_invalid_token'}, transports=['websocket'])
        await sio.wait()
    except Exception as e:
        print(f"Connection Exception: {e}")

if __name__ == '__main__':
    asyncio.run(main())
