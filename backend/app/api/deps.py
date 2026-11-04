from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.user import UserRole

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
DbDep = Annotated[Session, Depends(get_db)]


def current_user(
    request: Request, db: DbDep, bearer: Annotated[str | None, Depends(oauth2)]
) -> User:
    """Authentification : en-tête Bearer (scripts/API) ou cookie HttpOnly (navigateur)."""
    token = bearer or request.cookies.get(get_settings().session_cookie_name)
    sub = decode_access_token(token) if token else None
    user = db.get(User, int(sub)) if sub and sub.isdigit() else None
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Jeton invalide.", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]
