from jose import jwt, JWTError
from core.config import Settings
from domain.models import User

class AuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
    
    async def verify_token(self, token: str) -> User | None:
        try:
            payload = jwt.decode(
                token,
                self.settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=f"{self.settings.supabase_url}/auth/v1"
            )
            return User(
                id=payload["sub"],
                username=payload.get("user_metadata", {}).get("username", "User"),
                avatar_url=payload.get("user_metadata", {}).get("avatar_url"),
                is_anonymous=False
            )
        except JWTError:
            return None
        
    