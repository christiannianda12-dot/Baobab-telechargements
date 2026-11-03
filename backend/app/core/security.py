"""Hachage des mots de passe (bcrypt) et jetons JWT."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    # bcrypt ne traite que 72 octets : la validation d'entrée limite la longueur en amont.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = data.get("sub")
    return sub if isinstance(sub, str) else None
