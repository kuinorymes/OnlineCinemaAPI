import enum
from datetime import datetime, timezone, date, timedelta

from typing import List, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Enum, Boolean, DateTime, ForeignKey, Date, Text

from src.database.models.base import Base
from src.database.models.utils import generate_token


class UserGroupEnum(enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(enum.Enum):
    MAN = "man"
    WOMAN = "woman"


class UserGroupModel(Base):
    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[GenderEnum] = mapped_column(Enum(UserGroupEnum), nullable=False, unique=True)

    users: Mapped[List["UserModel"]] = relationship("UserModel", back_populates="group")


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False)
    group: Mapped[UserGroupModel] = relationship("UserGroupModel", back_populates="users")

    profile: Mapped[Optional["UserProfileModel"]] = relationship(
        "UserProfileModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    activation_token: Mapped[Optional["ActivationTokenModel"]] = relationship(
        "ActivationTokenModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_token: Mapped[Optional["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[List["RefreshTokenModel"]] = relationship(
        "RefreshTokenModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )



class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gender: Mapped[Optional[GenderEnum]] = mapped_column(Enum(GenderEnum), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user: Mapped[UserModel] = relationship("UserModel", back_populates="profile")


class TokenBaseModel(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=24)
    )
    token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        default=generate_token,
    )


class ActivationTokenModel(TokenBaseModel):
    __tablename__ = "activation_tokens"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    user: Mapped[UserModel] = relationship("UserModel", back_populates="activation_token")


class PasswordResetToken(TokenBaseModel):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    user: Mapped[UserModel] = relationship("UserModel", back_populates="password_reset_token")


class RefreshTokenModel(TokenBaseModel):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    user: Mapped[UserModel] = relationship("UserModel", back_populates="refresh_tokens")
