from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.core.config import get_settings
from app.core.rate_limit import auth_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.models.user import UserRole
from app.schemas.auth import Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["authentification"])

# Hash factice pour égaliser le temps de réponse quand l'email est inconnu.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


@router.post(
    "/register", response_model=UserOut, status_code=201, dependencies=[Depends(auth_rate_limit)]
)
def register(payload: UserCreate, db: DbDep):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet email est déjà utilisé.")
    # Le tout premier compte devient administrateur (installation locale).
    is_first = db.scalar(select(User.id).limit(1)) is None
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN if is_first else UserRole.USER,
    )
    db.add(user)
    db.commit()
    return user


@router.post("/login", response_model=Token, dependencies=[Depends(auth_rate_limit)])
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbDep, response: Response):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    ok = verify_password(form.password, user.hashed_password if user else _DUMMY_HASH)
    if not (user and ok and user.is_active):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants incorrects.")
    token = create_access_token(str(user.id))
    st = get_settings()
    response.set_cookie(
        st.session_cookie_name,
        token,
        max_age=st.access_token_minutes * 60,
        httponly=True,
        secure=st.cookie_secure_effective,
        samesite=st.cookie_samesite,
        path="/",
    )
    return Token(
        access_token=token
    )  # le navigateur utilise le cookie ; le corps sert aux clients API/scripts


@router.post("/logout", status_code=204)
def logout(response: Response):
    st = get_settings()
    response.delete_cookie(
        st.session_cookie_name,
        path="/",
        secure=st.cookie_secure_effective,
        httponly=True,
        samesite=st.cookie_samesite,
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
