from repositories.chat_repository import ChatRepository
from infrastructure.redis_pubsub import RedisBroadcaster
import firebase_admin
from firebase_admin import messaging, credentials
import os

class NotificationService:
    def __init__(self, repo: ChatRepository):
        self.repo = repo
        self._firebase_enabled = False
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if cred_path and not firebase_admin._apps:
            try:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                self._firebase_enabled = True
            except Exception:
                pass
    
    async def _send_push(self, user_id: str, title: str, body: str, data: dict):
        if not self._firebase_enabled:
            return
        tokens = await self.repo.get_user_devices(user_id)
        if not tokens:
            return
        msg = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
            tokens=tokens
        )
        try:
            messaging.send_multicast(msg)
        except Exception:
            pass
    
    async def notify_mention(self, user_id: str, sender: str, room: str, preview: str):
        await self.repo.save_notification(
            user_id, "mention", f"{sender} mentioned you in {room}",
            preview[:100], {"room": room}
        )
        await self._send_push(user_id, f"{sender} mentioned you", preview[:100], {"type": "mention", "room": room})
    
    async def notify_reply(self, user_id: str, sender: str, room: str, preview: str):
        await self.repo.save_notification(
            user_id, "reply", f"{sender} replied to you in {room}",
            preview[:100], {"room": room}
        )
        await self._send_push(user_id, f"{sender} replied to you", preview[:100], {"type": "reply", "room": room})