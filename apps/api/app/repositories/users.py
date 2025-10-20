from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import hash_password, verify_password
from ..domain.users import User, UserCreate
from ..models.user import UserModel


class UsersRepository(Protocol):
    """Persistence interface for user records."""

    async def create(self, payload: UserCreate) -> User: ...

    async def get(self, user_id: UUID) -> User | None: ...

    async def list(self) -> list[User]: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def touch_last_login(self, user_id: UUID) -> User | None: ...

    async def verify_credentials(self, email: str, password: str) -> User | None: ...


class InMemoryUsersRepository:
    """Simplistic in-memory repository for prototyping the API surface."""

    def __init__(self) -> None:
        self._users: dict[UUID, User] = {}
        self._email_index: dict[str, UUID] = {}
        self._password_hashes: dict[UUID, str] = {}

    async def create(self, payload: UserCreate) -> User:
        normalized_email = payload.email.lower()
        if normalized_email in self._email_index:
            raise ValueError("user with email already exists")
        data = payload.model_dump(exclude={"password"})
        user = User(**data)
        self._users[user.id] = user
        self._email_index[normalized_email] = user.id
        self._password_hashes[user.id] = hash_password(payload.password)
        return user

    async def get(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    async def list(self) -> list[User]:
        return list(self._users.values())

    async def get_by_email(self, email: str) -> User | None:
        user_id = self._email_index.get(email.lower())
        if not user_id:
            return None
        return self._users.get(user_id)

    async def touch_last_login(self, user_id: UUID) -> User | None:
        user = self._users.get(user_id)
        if not user:
            return None
        updated = user.model_copy(
            update={
                "last_login_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )
        self._users[user_id] = updated
        return updated

    async def verify_credentials(self, email: str, password: str) -> User | None:
        user = await self.get_by_email(email)
        if not user:
            return None
        hashed = self._password_hashes.get(user.id)
        if not hashed:
            return None
        if not verify_password(password, hashed):
            return None
        return user


class SqlAlchemyUsersRepository:
    """SQLAlchemy-backed repository for user persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, payload: UserCreate) -> User:
        normalized_email = payload.email.lower()
        model = UserModel(
            email=normalized_email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
        self._session.add(model)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ValueError("user with email already exists") from exc
        await self._session.refresh(model)
        return self._to_domain(model)

    async def get(self, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def list(self) -> list[User]:
        result = await self._session.execute(select(UserModel))
        return [self._to_domain(model) for model in result.scalars().all()]

    async def get_by_email(self, email: str) -> User | None:
        normalized_email = email.lower()
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == normalized_email)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def touch_last_login(self, user_id: UUID) -> User | None:
        now = datetime.utcnow()
        result = await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(last_login_at=now, updated_at=now)
            .returning(UserModel)
        )
        model = result.scalar_one_or_none()
        if not model:
            await self._session.commit()
            return None
        await self._session.commit()
        return self._to_domain(model)

    async def verify_credentials(self, email: str, password: str) -> User | None:
        normalized_email = email.lower()
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == normalized_email)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        if not verify_password(password, model.password_hash):
            return None
        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            full_name=model.full_name,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login_at=model.last_login_at,
        )
