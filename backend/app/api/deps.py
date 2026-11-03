from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.user import UserRole

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
DbDep = Annotated[Session, Depends(get_db)]


def current_user(db: DbDep, token: Annotated[str, Depends(oauth2)]) -> User:
    sub = decode_access_token(token)
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
