import json
import nats


class NATSManager:  
    def __init__(self):
        self.nc = None
        self.connected = False

    async def connect(self):
        if not self.connected:
            self.nc = await nats.connect("nats://localhost:4222")
            self.connected = True
            print("Подключен к NATS")

    async def publish(self, subject: str, data: dict):
        if not self.connected:
            await self.connect()
        if self.connected:
            message = json.dumps(data, default=str)
            await self.nc.publish(subject, message.encode())
            print("Опубликовано в NATS")

    async def subscribe(self, subject: str, callback):
        if not self.connected:
            await self.connect()     
        if self.connected:
            await self.nc.subscribe(subject, cb=callback)
            print("Подписан на NATS канал")

    async def close(self):
        if self.connected and self.nc:
            await self.nc.close()
            self.connected = False
            print("Соединение с NATS закрыто")