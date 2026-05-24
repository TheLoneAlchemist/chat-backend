from fastapi import APIRouter, Depends, HTTPException, Query,Body
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from infrastructure.database import get_supabase
from typing import Optional
from infrastructure.database import get_supabase
from repositories.chat_repository import ChatRepository
from services.auth_service import AuthService
from services.chat_service import ChatService
from core.config import get_settings
from pydantic import BaseModel, Field
from services.guest_service import GuestService

router = APIRouter(prefix="/api")

security = HTTPBearer(auto_error=False)

def get_repo():
    return ChatRepository(get_supabase())

def get_auth_service():
    return AuthService(get_settings())

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Validate Supabase JWT from Authorization header.

    Header:
    Authorization: Bearer <token>
    """

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token"
        )

    token = credentials.credentials

    user = await auth_service.verify_token(token)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    return user

def get_chat_service(repo: ChatRepository = Depends(get_repo)):
    return ChatService(repo, None)  # Inject notifier if needed



@router.get("/rooms")
async def list_rooms(repo: ChatRepository = Depends(get_repo)):
    def _run():
        return get_supabase().table("chat_rooms").select("*,categories(name,slug)").eq("is_active", True).execute()
    import asyncio
    res = await asyncio.to_thread(_run)
    return res.data or []

@router.get("/rooms/{slug}/messages")
async def get_messages(
    slug: str,
    before: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    repo: ChatRepository = Depends(get_repo)
):
    room = await repo.get_room_by_slug(slug)
    if not room:
        raise HTTPException(404, "Room not found")
    
    def _run():
        q = get_supabase().table("messages").select(
            "id,room_id,user_id,guest_id,content,content_type,parent_id,metadata,edited_at,is_deleted,created_at,profiles(username,avatar_url),guests(username)"
        ).eq("room_id", room["id"]).eq("is_deleted", False).order("created_at", desc=True).limit(limit)
        if before:
            q = q.lt("created_at", before)
        return q.execute()
    import asyncio
    res = await asyncio.to_thread(_run)
    messages = list(reversed(res.data or []))
    return {"messages": messages, "has_more": len(res.data) == limit}

@router.get("/search")
async def search(
    q: str,
    room: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: ChatRepository = Depends(get_repo)
):
    room_id = None
    if room:
        r = await repo.get_room_by_slug(room)
        if r:
            room_id = r["id"]
    results = await repo.search_messages(q, room_id, limit, offset)
    return {"results": results, "query": q, "count": len(results)}

@router.get("/threads/{message_id}")
async def get_thread(message_id: str, repo: ChatRepository = Depends(get_repo)):
    parent = await repo.get_message(message_id)
    if not parent:
        raise HTTPException(404, "Not found")
    replies = await repo.get_thread(message_id)
    return {"parent": parent, "replies": replies}


class GuestCreateRequest(BaseModel):
    guest_id: str
    username: str = Field(..., min_length=3, max_length=30)
    secret: str | None = None   # generated on device, never sent again in plaintext

@router.post("/guests")
async def register_guest(
    req: GuestCreateRequest,
    repo: ChatRepository = Depends(get_repo)
):
    # Prevent overwriting existing guest
    existing = await repo.get_guest_by_id(req.guest_id)
    if existing:
        raise HTTPException(409, "Guest ID already registered")
    
    svc = GuestService(repo)
    user = await svc.create_guest(req.guest_id, req.username, req.secret)
    return {"id": user.id, "username": user.username}

@router.post("/migrate-guest")
async def migrate_guest(
    guest_id: str = Body(..., embed=True),
    repo: ChatRepository = Depends(get_repo),
    user=Depends(get_current_user)   # requires Supabase JWT
):
    """Link guest messages to the newly registered user"""
    await repo.transfer_guest_messages(guest_id, user.id)
    # Optionally delete guest row
    return {"status": "migrated", "user_id": user.id}

@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    """Fetch current registered user profile"""
    supabase = get_supabase()
    def _run():
        return supabase.table("profiles").select("*").eq("id", user["sub"]).single().execute()
    import asyncio
    res = await asyncio.to_thread(_run)
    return res.data if res.data else {}