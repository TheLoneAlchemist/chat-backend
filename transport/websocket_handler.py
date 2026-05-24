import json
from fastapi import WebSocket, WebSocketDisconnect
from domain.models import WsMessage, MessagePayload, EditPayload, DeletePayload, TypingPayload, ReadPayload
from services.guest_service import GuestService
from services.auth_service import AuthService
from services.chat_service import ChatService
from transport.connection_manager import ConnectionManager
from infrastructure.redis_pubsub import RedisBroadcaster

class WebSocketHandler:
    def __init__(
        self,
        manager: ConnectionManager,
        redis: RedisBroadcaster,
        guest_svc: GuestService,
        auth_svc: AuthService,
        chat_svc: ChatService
    ):
        self.manager = manager
        self.redis = redis
        self.guest_svc = guest_svc
        self.auth_svc = auth_svc
        self.chat_svc = chat_svc
        
        # Subscribe to Redis broadcasts
        self.redis.on_message(self._handle_redis_message)
    
    async def _handle_redis_message(self, data: dict):
        room = data["room"]
        payload = data["payload"]
        exclude = data.get("exclude")
        await self.manager.broadcast(room, payload, exclude)
    
    async def handle(self, ws: WebSocket):
        token = ws.query_params.get("token")
        guest_id = ws.query_params.get("guest_id")
        guest_secret = ws.query_params.get("guest_secret")

        user = None
        if token:
            user = await self.auth_svc.verify_token(token)
        elif guest_id:
            user = await self.guest_svc.authenticate_guest(guest_id, guest_secret)
        
        if not user:
            await ws.close(code=4001, reason="Need token or valid guest_id")
            return
        
        user_id = user.id
        await self.manager.connect(ws, user_id, {
            "username": user.username,
            "avatar_url": user.avatar_url,
            "is_anonymous": user.is_anonymous
        })
        
        # Confirm connection
        await self.manager.send_to_user(user_id, {
            "t": "conn",
            "d": {"uid": user_id, "un": user.username, "anon": user.is_anonymous}
        })
        
        # Auto-join global
        await self.manager.join(user_id, "global")
        await self.redis.publish("global", {
            "t": "join",
            "d": {"uid": user_id, "un": user.username, "room": "global"}
        })
        
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    envelope = json.loads(raw)
                    await self._route(user, envelope)
                except json.JSONDecodeError:
                    await self.manager.send_to_user(user_id, {
                        "t": "err", "d": {"msg": "Invalid JSON"}
                    })
                except Exception as e:
                    await ws.send_json({
                        "t": "err",
                        "d": {"msg": str(e)}
                    })
        except WebSocketDisconnect:
            pass
        finally:
            # Cleanup
            rooms = list(self.manager.user_rooms.get(user_id, set()))
            await self.manager.disconnect(user_id)
            for room in rooms:
                await self.redis.publish(room, {
                    "t": "left",
                    "d": {"uid": user_id, "room": room}
                })
    
    async def _route(self, user, envelope: dict):
        t = envelope.get("t")
        d = envelope.get("d", {})
        uid = user.id
        
        if t == "join":
            room = d.get("room", "global")
            await self.manager.join(uid, room)
            await self.redis.publish(room, {
                "t": "join", "d": {"uid": uid, "un": user.username, "room": room}
            }, exclude=uid)
        
        elif t == "msg":
            if not self.chat_svc.check_rate_limit(uid):
                await self.manager.send_to_user(uid, {"t": "err", "d": {"msg": "Rate limited"}})
                return
            payload = MessagePayload(**d)
            msg = await self.chat_svc.send_message(user, payload)
            await self.redis.publish(payload.room, {
                "t": "msg", "d": msg
            }, exclude=uid)
        
        elif t == "edit":
            payload = EditPayload(**d)
            try:
                res = await self.chat_svc.edit_message(user, payload.message_id, payload.content)
                await self.redis.publish(res["room"], {
                    "t": "edit", "d": res
                })
            except Exception as e:
                await self.manager.send_to_user(uid, {"t": "err", "d": {"msg": str(e)}})
        
        elif t == "del":
            payload = DeletePayload(**d)
            try:
                res = await self.chat_svc.delete_message(user, payload.message_id)
                await self.redis.publish(res["room"], {
                    "t": "del", "d": res
                })
            except Exception as e:
                await self.manager.send_to_user(uid, {"t": "err", "d": {"msg": str(e)}})
        
        elif t == "type":
            payload = TypingPayload(**d)
            await self.redis.publish(payload.room, {
                "t": "type",
                "d": {"uid": uid, "un": user.username, "typing": payload.typing, "room": payload.room}
            }, exclude=uid)
        
        elif t == "read":
            payload = ReadPayload(**d)
            # Could track in Redis here
            pass
        
        elif t == "ping":
            await self.manager.send_to_user(uid, {"t": "pong"})