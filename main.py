import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import get_settings
from infrastructure.database import get_supabase
from infrastructure.redis_pubsub import RedisBroadcaster
from repositories.chat_repository import ChatRepository
from services.guest_service import GuestService
from services.auth_service import AuthService
from services.chat_service import ChatService
from services.notification_service import NotificationService
from transport.connection_manager import ConnectionManager
from transport.websocket_handler import WebSocketHandler
from transport import rest_routes

settings = get_settings()

# Singletons
manager = ConnectionManager()
redis_broadcaster = RedisBroadcaster(settings.redis_url)
repo = ChatRepository(get_supabase())
notifier = NotificationService(repo)
chat_service = ChatService(repo, notifier)
guest_service = GuestService(repo)
auth_service = AuthService(settings)
ws_handler = WebSocketHandler(manager, redis_broadcaster, guest_service, auth_service, chat_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Redis listener as background task
    task = asyncio.create_task(redis_broadcaster.start())
    yield
    task.cancel()
    await redis_broadcaster.close()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_routes.router)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_handler.handle(ws)

@app.get("/health")
async def health():
    return {"status": "ok"}

# This is what you pass to uvicorn: main:socket_app
# uvicorn main:socket_app --host 0.0.0.0 --port 8000 --workers 4