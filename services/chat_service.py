import time
import re
from typing import Optional
from domain.models import User, MessagePayload
from repositories.chat_repository import ChatRepository
from services.notification_service import NotificationService

MENTION_RE = re.compile(r'@(\w{3,30})')

class ChatService:
    def __init__(self, repo: ChatRepository, notifier: NotificationService):
        self.repo = repo
        self.notifier = notifier
        self._last_message: dict[str, float] = {}
    
    def check_rate_limit(self, user_id: str) -> bool:
        now = time.time()
        last = self._last_message.get(user_id, 0)
        if now - last < 0.5:
            return False
        self._last_message[user_id] = now
        return True
    
    async def send_message(self, user: User, payload: MessagePayload) -> dict:
        room = await self.repo.get_room_by_slug(payload.room)
        if not room:
            raise ValueError("Room not found")
        
        # Save message
        msg = await self.repo.insert_message(
            room_id=room["id"],
            content=payload.content,
            user_id=user.id if not user.is_anonymous else None,
            guest_id=user.id if user.is_anonymous else None,
            parent_id=payload.parent_id,
            metadata={"quote_id": payload.quote_id} if payload.quote_id else {}
        )
        if not msg:
            raise ValueError("Failed to save message")
        
        # Mentions
        mentions = MENTION_RE.findall(payload.content)
        for username in mentions:
            target = await self.repo.get_user_by_username(username)
            if target and target["id"] != user.id:
                await self.repo.create_mention(msg["id"], target["id"])
                # Notify offline registered users only
                await self.notifier.notify_mention(
                    target["id"], user.username, room["name"], payload.content
                )
        
        # Reply notification
        if payload.parent_id:
            parent = await self.repo.get_message(payload.parent_id)
            if parent and parent.get("user_id") and parent["user_id"] != user.id:
                await self.notifier.notify_reply(
                    parent["user_id"], user.username, room["name"], payload.content
                )
        
        return {
            "id": msg["id"],
            "room_id": room["id"],
            "room": payload.room,
            "content": msg["content"],
            "user_id": user.id,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "parent_id": payload.parent_id,
            "quote_id": payload.quote_id,
            "edited_at": None,
            "is_deleted": False,
            "created_at": msg["created_at"],
            "mentions": mentions
        }
    
    async def edit_message(self, user: User, message_id: str, new_content: str) -> dict:
        msg = await self.repo.get_message(message_id)
        if not msg:
            raise ValueError("Message not found")
        
        # Authorization
        sender_field = "guest_id" if user.is_anonymous else "user_id"
        if msg.get(sender_field) != user.id:
            raise PermissionError("Not authorized")
        
        await self.repo.update_message(message_id, new_content)
        return {
            "message_id": message_id,
            "content": new_content,
            "room": msg["chat_rooms"]["slug"],
            "edited_at": "now()"
        }
    
    async def delete_message(self, user: User, message_id: str) -> dict:
        msg = await self.repo.get_message(message_id)
        if not msg:
            raise ValueError("Message not found")
        
        sender_field = "guest_id" if user.is_anonymous else "user_id"
        if msg.get(sender_field) != user.id:
            raise PermissionError("Not authorized")
        
        await self.repo.soft_delete_message(message_id)
        return {
            "message_id": message_id,
            "room": msg["chat_rooms"]["slug"]
        }