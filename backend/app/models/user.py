import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(CreatedAtMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
