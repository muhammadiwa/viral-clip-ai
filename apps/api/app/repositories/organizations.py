from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.organizations import (
    Membership,
    MembershipCreateRequest,
    MembershipRole,
    MembershipStatus,
    MembershipUpdateRequest,
    Organization,
    OrganizationCreate,
)
from ..models.organization import MembershipModel, OrganizationModel


class OrganizationsRepository(Protocol):
    """Persistence interface for organizations and memberships."""

    async def create(
        self,
        payload: OrganizationCreate,
        *,
        owner_user_id: UUID | None = None,
    ) -> tuple[Organization, Membership | None]: ...

    async def list(self) -> list[Organization]: ...

    async def get(self, org_id: UUID) -> Organization | None: ...

    async def list_for_user(self, user_id: UUID) -> list[Organization]: ...

    async def add_member(
        self,
        org_id: UUID,
        payload: MembershipCreateRequest,
    ) -> Membership | None: ...

    async def list_members(self, org_id: UUID) -> list[Membership]: ...

    async def get_membership(
        self,
        org_id: UUID,
        membership_id: UUID,
    ) -> Membership | None: ...

    async def update_membership(
        self,
        org_id: UUID,
        membership_id: UUID,
        payload: MembershipUpdateRequest,
    ) -> Membership | None: ...

    async def find_membership_by_user(
        self, org_id: UUID, user_id: UUID
    ) -> Membership | None: ...


class InMemoryOrganizationsRepository:
    """In-memory organization repository suitable for early prototyping."""

    def __init__(self) -> None:
        self._organizations: dict[UUID, Organization] = {}
        self._memberships: dict[UUID, Membership] = {}
        self._org_memberships: dict[UUID, set[UUID]] = {}
        self._user_memberships: dict[UUID, set[UUID]] = {}
        self._slug_index: dict[str, UUID] = {}

    async def create(
        self,
        payload: OrganizationCreate,
        *,
        owner_user_id: UUID | None = None,
    ) -> tuple[Organization, Membership | None]:
        slug = payload.slug or self._generate_slug(payload.name)
        slug = self._ensure_unique_slug(slug)
        org = Organization(**payload.model_dump(exclude_none=True), slug=slug)
        self._organizations[org.id] = org
        self._slug_index[slug] = org.id
        self._org_memberships[org.id] = set()
        owner_membership: Membership | None = None
        if owner_user_id:
            owner_membership = await self._create_membership(
                org_id=org.id,
                payload=MembershipCreateRequest(
                    user_id=owner_user_id,
                    role=MembershipRole.OWNER,
                    status=MembershipStatus.ACTIVE,
                    invited_by_user_id=owner_user_id,
                ),
            )
        return org, owner_membership

    async def list(self) -> list[Organization]:
        return list(self._organizations.values())

    async def get(self, org_id: UUID) -> Organization | None:
        return self._organizations.get(org_id)

    async def list_for_user(self, user_id: UUID) -> list[Organization]:
        membership_ids = self._user_memberships.get(user_id, set())
        organizations: list[Organization] = []
        for membership_id in membership_ids:
            membership = self._memberships.get(membership_id)
            if not membership:
                continue
            org = self._organizations.get(membership.org_id)
            if org:
                organizations.append(org)
        return organizations

    async def add_member(
        self,
        org_id: UUID,
        payload: MembershipCreateRequest,
    ) -> Membership | None:
        if org_id not in self._organizations:
            return None
        existing = await self.find_membership_by_user(org_id, payload.user_id)
        if existing:
            raise ValueError("user already a member of this organization")
        return await self._create_membership(org_id=org_id, payload=payload)

    async def list_members(self, org_id: UUID) -> list[Membership]:
        membership_ids = self._org_memberships.get(org_id, set())
        return [self._memberships[mid] for mid in membership_ids if mid in self._memberships]

    async def get_membership(
        self,
        org_id: UUID,
        membership_id: UUID,
    ) -> Membership | None:
        membership = self._memberships.get(membership_id)
        if membership and membership.org_id == org_id:
            return membership
        return None

    async def update_membership(
        self,
        org_id: UUID,
        membership_id: UUID,
        payload: MembershipUpdateRequest,
    ) -> Membership | None:
        membership = await self.get_membership(org_id, membership_id)
        if not membership:
            return None
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        if "joined_at" in update_data and update_data["joined_at"] is None:
            update_data.pop("joined_at")
        if update_data.get("status") == MembershipStatus.ACTIVE and "joined_at" not in update_data:
            update_data["joined_at"] = datetime.utcnow()
        updated = membership.model_copy(
            update={
                **update_data,
                "updated_at": datetime.utcnow(),
            }
        )
        self._memberships[membership_id] = updated
        return updated

    async def find_membership_by_user(
        self, org_id: UUID, user_id: UUID
    ) -> Membership | None:
        membership_ids = self._org_memberships.get(org_id, set())
        for membership_id in membership_ids:
            membership = self._memberships.get(membership_id)
            if membership and membership.user_id == user_id:
                return membership
        return None

    async def _create_membership(
        self,
        *,
        org_id: UUID,
        payload: MembershipCreateRequest,
    ) -> Membership:
        joined_at = None
        if payload.status == MembershipStatus.ACTIVE:
            joined_at = datetime.utcnow()
        membership = Membership(
            org_id=org_id,
            user_id=payload.user_id,
            role=payload.role,
            status=payload.status,
            invited_by_user_id=payload.invited_by_user_id,
            joined_at=joined_at,
        )
        self._memberships[membership.id] = membership
        self._org_memberships.setdefault(org_id, set()).add(membership.id)
        self._user_memberships.setdefault(payload.user_id, set()).add(membership.id)
        return membership

    def _generate_slug(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug or "org"

    def _ensure_unique_slug(self, slug: str) -> str:
        base = slug
        suffix = 2
        while slug in self._slug_index:
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug


class SqlAlchemyOrganizationsRepository:
    """SQLAlchemy-backed repository for organizations and memberships."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        payload: OrganizationCreate,
        *,
        owner_user_id: UUID | None = None,
    ) -> tuple[Organization, Membership | None]:
        slug = payload.slug or self._generate_slug(payload.name)
        slug = await self._ensure_unique_slug(slug)
        model = OrganizationModel(name=payload.name, slug=slug)
        self._session.add(model)
        await self._session.flush()

        owner_membership_model: MembershipModel | None = None
        if owner_user_id:
            owner_membership_model = await self._create_membership(
                org_id=model.id,
                payload=MembershipCreateRequest(
                    user_id=owner_user_id,
                    role=MembershipRole.OWNER,
                    status=MembershipStatus.ACTIVE,
                    invited_by_user_id=owner_user_id,
                ),
            )

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ValueError("organization slug already exists") from exc
        await self._session.refresh(model)
        owner_membership = None
        if owner_membership_model:
            await self._session.refresh(owner_membership_model)
            owner_membership = self._membership_to_domain(owner_membership_model)
        return self._organization_to_domain(model), owner_membership

    async def list(self) -> list[Organization]:
        result = await self._session.execute(select(OrganizationModel))
        return [self._organization_to_domain(model) for model in result.scalars().all()]

    async def get(self, org_id: UUID) -> Organization | None:
        result = await self._session.execute(
            select(OrganizationModel).where(OrganizationModel.id == org_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._organization_to_domain(model)

    async def list_for_user(self, user_id: UUID) -> list[Organization]:
        stmt = (
            select(OrganizationModel)
            .join(MembershipModel, MembershipModel.org_id == OrganizationModel.id)
            .where(MembershipModel.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return [self._organization_to_domain(model) for model in result.scalars().all()]

    async def add_member(
        self,
        org_id: UUID,
        payload: MembershipCreateRequest,
    ) -> Membership | None:
        org = await self.get(org_id)
        if org is None:
            return None
        existing = await self.find_membership_by_user(org_id, payload.user_id)
        if existing:
            raise ValueError("user already a member of this organization")
        membership_model = await self._create_membership(org_id=org_id, payload=payload)
        await self._session.commit()
        await self._session.refresh(membership_model)
        return self._membership_to_domain(membership_model)

    async def list_members(self, org_id: UUID) -> list[Membership]:
        result = await self._session.execute(
            select(MembershipModel).where(MembershipModel.org_id == org_id)
        )
        return [self._membership_to_domain(model) for model in result.scalars().all()]

    async def get_membership(
        self,
        org_id: UUID,
        membership_id: UUID,
    ) -> Membership | None:
        result = await self._session.execute(
            select(MembershipModel).where(
                MembershipModel.id == membership_id,
                MembershipModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._membership_to_domain(model)

    async def update_membership(
        self,
        org_id: UUID,
        membership_id: UUID,
        payload: MembershipUpdateRequest,
    ) -> Membership | None:
        result = await self._session.execute(
            select(MembershipModel).where(
                MembershipModel.id == membership_id,
                MembershipModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        if payload.role is not None:
            model.role = payload.role.value
        if payload.status is not None:
            model.status = payload.status.value
            if (
                payload.status == MembershipStatus.ACTIVE
                and payload.joined_at is None
                and model.joined_at is None
            ):
                model.joined_at = datetime.utcnow()
        if "joined_at" in update_data:
            model.joined_at = payload.joined_at
        model.updated_at = datetime.utcnow()

        await self._session.commit()
        await self._session.refresh(model)
        return self._membership_to_domain(model)

    async def find_membership_by_user(
        self, org_id: UUID, user_id: UUID
    ) -> Membership | None:
        result = await self._session.execute(
            select(MembershipModel).where(
                MembershipModel.org_id == org_id,
                MembershipModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._membership_to_domain(model)

    async def _create_membership(
        self,
        *,
        org_id: UUID,
        payload: MembershipCreateRequest,
    ) -> MembershipModel:
        joined_at = payload.joined_at
        if joined_at is None and payload.status == MembershipStatus.ACTIVE:
            joined_at = datetime.utcnow()
        model = MembershipModel(
            org_id=org_id,
            user_id=payload.user_id,
            role=payload.role.value,
            status=payload.status.value,
            invited_by_user_id=payload.invited_by_user_id,
            joined_at=joined_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ValueError("user already a member of this organization") from exc
        return model

    @staticmethod
    def _organization_to_domain(model: OrganizationModel) -> Organization:
        return Organization(
            id=model.id,
            name=model.name,
            slug=model.slug,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _membership_to_domain(model: MembershipModel) -> Membership:
        return Membership(
            id=model.id,
            org_id=model.org_id,
            user_id=model.user_id,
            role=MembershipRole(model.role),
            status=MembershipStatus(model.status),
            invited_by_user_id=model.invited_by_user_id,
            invited_at=model.invited_at,
            joined_at=model.joined_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _generate_slug(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug or "org"

    async def _ensure_unique_slug(self, slug: str) -> str:
        base = slug
        suffix = 2
        while await self._slug_exists(slug):
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    async def _slug_exists(self, slug: str) -> bool:
        result = await self._session.execute(
            select(OrganizationModel.id).where(OrganizationModel.slug == slug)
        )
        return result.scalar_one_or_none() is not None
