from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.organizations import MembershipRole, MembershipStatus, MembershipCreateRequest, OrganizationListResponse
from ...domain.pagination import PaginationParams
from ...domain.users import UserCreate, UserListResponse, UserResponse
from ...services.pagination import paginate_sequence
from ..dependencies import (
    get_idempotency_context,
    get_organizations_repository,
    get_users_repository,
    get_current_user,
    get_org_id,
    IdempotencyContext,
    get_pagination_params,
    require_org_role,
)
from ...repositories.organizations import OrganizationsRepository
from ...repositories.users import UsersRepository
from ...domain.users import User

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))])
async def create_user(
    payload: UserCreate,
    users_repo: UsersRepository = Depends(get_users_repository),
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> UserResponse:
    """
    Create a team member user (by owner/admin only).
    Team member will be added to the same organization as the creator.
    """
    cached = idempotency.get_response(UserResponse)
    if cached:
        return cached
    
    # Create user without owned_org_id (team member)
    try:
        user = await users_repo.create(payload, owned_org_id=None)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with email already exists",
        ) from exc
    
    # Add user to current organization with specified role
    role_value = payload.role or "viewer"
    try:
        role = MembershipRole(role_value)
    except ValueError:
        role = MembershipRole.VIEWER
    
    # Ensure team members cannot be OWNER
    if role == MembershipRole.OWNER:
        role = MembershipRole.ADMIN
    
    membership_payload = MembershipCreateRequest(
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
        invited_by_user_id=current_user.id,
    )
    
    try:
        await orgs_repo.add_member(org_id, membership_payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already belongs to organization",
        ) from exc
    
    response = UserResponse(data=user)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get("/users", response_model=UserListResponse)
async def list_users(
    users_repo: UsersRepository = Depends(get_users_repository),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> UserListResponse:
    users = await users_repo.list()
    paginated, meta = paginate_sequence(users, pagination)
    return UserListResponse(data=paginated, count=meta.count, pagination=meta)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    users_repo: UsersRepository = Depends(get_users_repository),
) -> UserResponse:
    user = await users_repo.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(data=user)


@router.get("/users/{user_id}/organizations", response_model=OrganizationListResponse)
async def list_user_organizations(
    user_id: UUID,
    users_repo: UsersRepository = Depends(get_users_repository),
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> OrganizationListResponse:
    user = await users_repo.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    organizations = await orgs_repo.list_for_user(user_id)
    paginated, meta = paginate_sequence(organizations, pagination)
    return OrganizationListResponse(data=paginated, count=meta.count, pagination=meta)
