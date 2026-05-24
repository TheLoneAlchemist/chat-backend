from fastapi import WebSocket
from typing import Dict, Set

class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.user_rooms: Dict[str, Set[str]] = {}
        self.room_users: Dict[str, Set[str]] = {}
        self.user_meta: Dict[str, dict] = {}
    
    async def connect(self, ws: WebSocket, user_id: str, meta: dict):
        await ws.accept()
        self.connections[user_id] = ws
        self.user_meta[user_id] = meta
        self.user_rooms[user_id] = set()
    
    async def disconnect(self, user_id: str):
        ws = self.connections.pop(user_id, None)
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
        
        rooms = self.user_rooms.pop(user_id, set())
        for room in rooms:
            self.room_users.get(room, set()).discard(user_id)
        self.user_meta.pop(user_id, None)
    
    async def join(self, user_id: str, room: str):
        self.user_rooms[user_id].add(room)
        self.room_users.setdefault(room, set()).add(user_id)
    
    async def leave(self, user_id: str, room: str):
        self.user_rooms[user_id].discard(room)
        self.room_users.get(room, set()).discard(user_id)
    
    async def broadcast(self, room: str, message: dict, exclude: str | None = None):
        users = self.room_users.get(room, set()).copy()
        for uid in users:
            if uid != exclude:
                await self.send_to_user(uid, message)
    
    async def send_to_user(self, user_id: str, message: dict):
        ws = self.connections.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                # Client disconnected abruptly
                pass