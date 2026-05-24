import asyncio
from supabase import Client
from domain.models import User

class ChatRepository:
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    # --- Guests ---
    
    async def get_guest_by_id(self, guest_id: str):
        def _run():
            return self.supabase.table("guests").select("id,username,secret_hash").eq("id", guest_id).maybe_single().execute()
        res = await asyncio.to_thread(_run)
        if not res or not res.data:
            return None
        return res.data 

    async def create_guest_with_id(self, guest_id: str, username: str, secret_hash: str | None):
        def _run():
            return self.supabase.table("guests").insert({
                "id": guest_id,
                "username": username,
                "secret_hash": secret_hash
            }).execute()
        return await asyncio.to_thread(_run)

    async def transfer_guest_messages(self, guest_id: str, user_id: str):
        """Call this later when the user upgrades from guest to registered"""
        def _run():
            return self.supabase.table("messages").update({
                "user_id": user_id,
                "guest_id": None
            }).eq("guest_id", guest_id).execute()
        return await asyncio.to_thread(_run)

    async def update_guest_seen(self, guest_id: str):
        def _run():
            return self.supabase.table("guests").update({
                "last_seen": "now()"
            }).eq("id", guest_id).execute()
        return await asyncio.to_thread(_run)
    
    # --- Rooms ---
    async def get_room_by_slug(self, slug: str):
        def _run():
            return self.supabase.table("chat_rooms").select("*").eq("slug", slug).limit(1).execute()
        res = await asyncio.to_thread(_run)
        if not res.data:
            return None
        return res.data[0]
    
    # --- Messages ---
    async def insert_message(self, room_id: str, content: str, 
                             user_id: str | None, guest_id: str | None,
                             parent_id: str | None, metadata: dict):
        def _run():
            return self.supabase.table("messages").insert({
                "room_id": room_id,
                "user_id": user_id,
                "guest_id": guest_id,
                "content": content,
                "parent_id": parent_id,
                "metadata": metadata
            }).execute()
        res = await asyncio.to_thread(_run)
        if not res.data:
            return None
        return res.data[0]
    
    async def get_message(self, message_id: str):
        def _run():
            return self.supabase.table("messages").select("*,chat_rooms(slug)").eq("id", message_id).single().execute()
        res = await asyncio.to_thread(_run)
        return res.data if res.data else None
    
    async def update_message(self, message_id: str, content: str):
        def _run():
            return self.supabase.table("messages").update({
                "content": content,
                "edited_at": "now()"
            }).eq("id", message_id).execute()
        return await asyncio.to_thread(_run)
    
    async def soft_delete_message(self, message_id: str):
        def _run():
            return self.supabase.table("messages").update({
                "is_deleted": True,
                "content": "[deleted]"
            }).eq("id", message_id).execute()
        return await asyncio.to_thread(_run)
    
    async def get_thread(self, parent_id: str):
        def _run():
            return self.supabase.table("messages").select(
                "*,profiles(username,avatar_url),guests(username)"
            ).eq("parent_id", parent_id).eq("is_deleted", False).order("created_at").execute()
        res = await asyncio.to_thread(_run)
        return res.data or []
    
    # --- Search ---
    async def search_messages(self, query: str, room_id: str | None, limit: int, offset: int):
        def _run():
            return self.supabase.rpc("search_messages", {
                "search_query": query,
                "room_filter": room_id,
                "result_limit": limit,
                "result_offset": offset
            }).execute()
        res = await asyncio.to_thread(_run)
        return res.data or []
    
    # --- Mentions ---
    async def get_user_by_username(self, username: str):
        def _run():
            return self.supabase.table("profiles").select("id,username").eq("username", username).single().execute()
        res = await asyncio.to_thread(_run)
        return res.data if res.data else None
    
    async def create_mention(self, message_id: str, user_id: str):
        def _run():
            return self.supabase.table("mentions").insert({
                "message_id": message_id, "mentioned_user_id": user_id
            }).execute()
        return await asyncio.to_thread(_run)
    
    # --- Notifications ---
    async def save_notification(self, user_id: str, n_type: str, title: str, body: str, data: dict):
        def _run():
            return self.supabase.table("notifications").insert({
                "user_id": user_id, "type": n_type, "title": title, "body": body, "data": data
            }).execute()
        return await asyncio.to_thread(_run)
    
    async def get_user_devices(self, user_id: str):
        def _run():
            return self.supabase.table("user_devices").select("fcm_token").eq("user_id", user_id).execute()
        res = await asyncio.to_thread(_run)
        return [d["fcm_token"] for d in (res.data or [])]