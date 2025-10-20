from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.organizations import (
    MembershipCreateRequest,
    MembershipListResponse,
    MembershipResponse,
    MembershipUpdateRequest,
    OrganizationCreate,
    OrganizationCreateRequest,
    OrganizationCreateResponse,
    OrganizationListResponse,
    OrganizationResponse,
)
from ...domain.pagination import PaginationParams
from ...repositories.organizations import OrganizationsRepository
from ...repositories.users import UsersRepository
from ...services.pagination import paginate_sequence
from ..dependencies import (
    get_idempotency_context,
    get_organizations_repository,
    get_users_repository,
    IdempotencyContext,
    get_pagination_params,
)

router = APIRouter(tags=["organizations"])


@router.post(
    "/organizations",
    response_model=OrganizationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    payload: OrganizationCreateRequest,
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    users_repo: UsersRepository = Depends(get_users_repository),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> OrganizationCreateResponse:
    cached = idempotency.get_response(OrganizationCreateResponse)
    if cached:
        return cached
    if payload.owner_user_id:
        owner = await users_repo.get(payload.owner_user_id)
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Owner user not found",
            )
    create_payload = OrganizationCreate(**payload.model_dump(exclude={"owner_user_id"}, exclude_none=True))
    try:
        organization, owner_membership = await orgs_repo.create(
            create_payload,
            owner_user_id=payload.owner_user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        ) from exc
    response = OrganizationCreateResponse(data=organization, owner_membership=owner_membership)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get("/organizations", response_model=OrganizationListResponse)
async def list_organizations(
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> OrganizationListResponse:
    organizations = await orgs_repo.list()
    paginated, meta = paginate_sequence(organizations, pagination)
    return OrganizationListResponse(data=paginated, count=meta.count, pagination=meta)


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
) -> OrganizationResponse:
    organization = await orgs_repo.get(org_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationResponse(data=organization)


@router.get("/organizations/{org_id}/members", response_model=MembershipListResponse)
async def list_members(
    org_id: UUID,
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> MembershipListResponse:
    organization = await orgs_repo.get(org_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    members = await orgs_repo.list_members(org_id)
    paginated, meta = paginate_sequence(members, pagination)
    return MembershipListResponse(data=paginated, count=meta.count, pagination=meta)


@router.post(
    "/organizations/{org_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    org_id: UUID,
    payload: MembershipCreateRequest,
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    users_repo: UsersRepository = Depends(get_users_repository),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> MembershipResponse:
    cached = idempotency.get_response(MembershipResponse)
    if cached:
        return cached
    organization = await orgs_repo.get(org_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    user = await users_repo.get(payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        membership = await orgs_repo.add_member(org_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already belongs to organization",
        ) from exc
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    response = MembershipResponse(data=membership)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get(
    "/organizations/{org_id}/members/{membership_id}",
    response_model=MembershipResponse,
)
async def get_member(
    org_id: UUID,
    membership_id: UUID,
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
) -> MembershipResponse:
    membership = await orgs_repo.get_membership(org_id, membership_id)
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    return MembershipResponse(data=membership)


@router.patch(
    "/organizations/{org_id}/members/{membership_id}",
    response_model=MembershipResponse,
)
async def update_member(
    org_id: UUID,
    membership_id: UUID,
    payload: MembershipUpdateRequest,
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
) -> MembershipResponse:
    membership = await orgs_repo.update_membership(org_id, membership_id, payload)
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    return MembershipResponse(data=membership)
