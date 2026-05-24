import json
import redis.asyncio as aioredis
from typing import Callable, Awaitable

class RedisBroadcaster:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self._handlers: list[Callable[[dict], Awaitable[None]]] = []
    
    async def start(self):
        await self.pubsub.psubscribe("room:*")
        async for message in self.pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    data = json.loads(message["data"])
                    for handler in self._handlers:
                        await handler(data)
                except Exception as e:
                    print(f"Redis handler error: {e}")
    
    def on_message(self, handler: Callable[[dict], Awaitable[None]]):
        self._handlers.append(handler)
    
    async def publish(self, room: str, payload: dict, exclude: str | None = None):
        await self.redis.publish(f"room:{room}", json.dumps({
            "room": room,
            "payload": payload,
            "exclude": exclude
        }))
    
    async def close(self):
        await self.pubsub.close()
        await self.redis.close()