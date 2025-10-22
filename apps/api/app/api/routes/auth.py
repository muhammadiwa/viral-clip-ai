from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.config import get_settings
from ...core.security import create_access_token
from ...domain.auth import RegisterRequest, RegisterResponse, TokenRequest, TokenResponse
from ...domain.organizations import OrganizationCreate, MembershipRole, MembershipStatus, MembershipCreateRequest
from ...domain.users import User, UserResponse, UserCreate
from ...repositories.users import UsersRepository
from ...repositories.organizations import OrganizationsRepository
from ..dependencies import get_current_user, get_users_repository, get_organizations_repository, get_idempotency_context, IdempotencyContext

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    users_repo: UsersRepository = Depends(get_users_repository),
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> RegisterResponse:
    """Register a new user with auto organization creation."""
    cached = idempotency.get_response(RegisterResponse)
    if cached:
        return cached
    
    # Check if email already exists
    existing_user = await users_repo.get_by_email(payload.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    
    # Create organization first
    org_payload = OrganizationCreate(name=payload.organization_name)
    try:
        organization, _ = await orgs_repo.create(org_payload, owner_user_id=None)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        ) from exc
    
    # Create user with owned_org_id
    user_payload = UserCreate(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    try:
        user = await users_repo.create(user_payload, owned_org_id=organization.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with email already exists",
        ) from exc
    
    # Create owner membership
    membership_payload = MembershipCreateRequest(
        user_id=user.id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
        invited_by_user_id=user.id,
    )
    membership = await orgs_repo.add_member(organization.id, membership_payload)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create membership",
        )
    
    # Generate access token
    settings = get_settings()
    access_token = create_access_token({
        "sub": str(user.id),
        "org_id": str(organization.id),
        "role": membership.role.value,
    })
    
    response = RegisterResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
        organization=organization,
        membership=membership,
    )
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(
    payload: TokenRequest,
    users_repo: UsersRepository = Depends(get_users_repository),
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
) -> TokenResponse:
    user = await users_repo.verify_credentials(payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    updated_user = await users_repo.touch_last_login(user.id)
    if updated_user is not None:
        user = updated_user
    
    # Get user's organization (either owned or membership)
    org_id = None
    role = None
    
    if user.owned_org_id:
        # User is owner
        org_id = user.owned_org_id
        role = "owner"
    else:
        # User is team member, find active membership
        orgs = await orgs_repo.list_for_user(user.id)
        if orgs:
            # Get first active membership
            members = await orgs_repo.list_members(orgs[0].id)
            for member in members:
                if member.user_id == user.id and member.status.value == "active":
                    org_id = member.org_id
                    role = member.role.value
                    break
    
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any organization",
        )
    
    settings = get_settings()
    access_token = create_access_token({
        "sub": str(user.id),
        "org_id": str(org_id),
        "role": role,
    })
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
    )


@router.get("/auth/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(data=current_user)
