import hashlib
import secrets
from domain.models import User
from repositories.chat_repository import ChatRepository

class GuestService:
    def __init__(self, repo: ChatRepository):
        self.repo = repo

    def _hash(self, s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()

    async def create_guest(self, guest_id: str, username: str, secret: str | None = None) -> User:
        secret_hash = self._hash(secret) if secret else None
        await self.repo.create_guest_with_id(guest_id, username, secret_hash)
        return User(id=guest_id, username=username, is_anonymous=True)

    async def authenticate_guest(self, guest_id: str, secret: str | None = None) -> User | None:
        guest = await self.repo.get_guest_by_id(guest_id)
        if not guest:
            return None
        
        # If a secret was set, the client MUST provide it
        if guest.get("secret_hash"):
            if not secret or self._hash(secret) != guest["secret_hash"]:
                return None
        
        return User(id=guest_id, username=guest["username"], is_anonymous=True)