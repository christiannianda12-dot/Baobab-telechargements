from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbDep
from app.core.config import get_settings
from app.models import APIProvider, User
from app.models.user import UserRole
from app.providers.registry import build_providers
from app.schemas.admin import AdminUserOut, AdminUserUpdate, ProviderOut

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: DbDep, _: AdminUser):
    return db.scalars(select(User).order_by(User.id)).all()


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, payload: AdminUserUpdate, db: DbDep, admin: AdminUser):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    demoting = user.role == UserRole.ADMIN and (
        payload.role == UserRole.USER or payload.is_active is False
    )
    if demoting:
        active_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        if active_admins <= 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Impossible de retirer le dernier administrateur actif."
            )
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    return user


@router.post("/providers/sync", response_model=list[ProviderOut])
def sync_providers(db: DbDep, _: AdminUser):
    """Aligne la table api_providers sur la configuration (une clé présente => activé)."""
    for p in build_providers(get_settings()):
        row = db.scalar(select(APIProvider).where(APIProvider.code == p.code))
        if row is None:
            row = APIProvider(code=p.code, name=p.name, kind=p.kind)
            db.add(row)
        row.base_url = p.base_url
        row.is_enabled = p.is_configured
        row.notes = p.describe()
    db.commit()
    return db.scalars(select(APIProvider).order_by(APIProvider.code)).all()


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(db: DbDep, _: AdminUser):
    return db.scalars(select(APIProvider).order_by(APIProvider.code)).all()
