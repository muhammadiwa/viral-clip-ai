from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.branding import (
    BrandAssetCreate,
    BrandAssetListResponse,
    BrandAssetResponse,
    BrandAssetUploadRequest,
    BrandAssetUploadResponse,
    BrandKitCreate,
    BrandKitListResponse,
    BrandKitResponse,
    BrandKitUpdate,
)
from ...domain.organizations import MembershipRole
from ...domain.pagination import PaginationParams, PaginationMeta
from ...repositories.branding import BrandKitRepository
from ...services.storage import MinioStorageService
from ...services.pagination import paginate_sequence
from ..dependencies import (
    get_active_membership,
    get_brand_kit_repository,
    get_org_id,
    get_storage_service,
    require_org_role,
    get_pagination_params,
)

router = APIRouter(prefix="/branding", tags=["branding"])


@router.post(
    "/brand-kits",
    response_model=BrandKitResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def create_brand_kit(
    payload: BrandKitCreate,
    repo: BrandKitRepository = Depends(get_brand_kit_repository),
    org_id: UUID = Depends(get_org_id),
) -> BrandKitResponse:
    brand_kit = await repo.create(org_id, payload)
    return BrandKitResponse(data=brand_kit)


@router.get(
    "/brand-kits",
    response_model=BrandKitListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_brand_kits(
    repo: BrandKitRepository = Depends(get_brand_kit_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
    include_archived: bool = False,
) -> BrandKitListResponse:
    brand_kits = await repo.list(org_id, include_archived=include_archived)
    paginated, meta = paginate_sequence(brand_kits, pagination)
    return BrandKitListResponse(data=paginated, count=meta.count, pagination=meta)


@router.get(
    "/brand-kits/{brand_kit_id}",
    response_model=BrandKitResponse,
    dependencies=[Depends(get_active_membership)],
)
async def get_brand_kit(
    brand_kit_id: UUID,
    repo: BrandKitRepository = Depends(get_brand_kit_repository),
    org_id: UUID = Depends(get_org_id),
) -> BrandKitResponse:
    brand_kit = await repo.get(org_id, brand_kit_id)
    if brand_kit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")
    return BrandKitResponse(data=brand_kit)


@router.patch(
    "/brand-kits/{brand_kit_id}",
    response_model=BrandKitResponse,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def update_brand_kit(
    brand_kit_id: UUID,
    payload: BrandKitUpdate,
    repo: BrandKitRepository = Depends(get_brand_kit_repository),
    org_id: UUID = Depends(get_org_id),
) -> BrandKitResponse:
    brand_kit = await repo.update(org_id, brand_kit_id, payload)
    if brand_kit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")
    return BrandKitResponse(data=brand_kit)


@router.post(
    "/brand-kits/{brand_kit_id}/assets:presign",
    response_model=BrandAssetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))],
)
async def presign_brand_asset(
    brand_kit_id: UUID,
    payload: BrandAssetUploadRequest,
    repo: BrandKitRepository = Depends(get_brand_kit_repository),
    storage: MinioStorageService = Depends(get_storage_service),
    org_id: UUID = Depends(get_org_id),
) -> BrandAssetUploadResponse:
    brand_kit = await repo.get(org_id, brand_kit_id)
    if brand_kit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")
    object_key = storage.generate_brand_asset_key(
        org_id=org_id, brand_kit_id=brand_kit_id, filename=payload.filename
    )
    upload_url = storage.generate_presigned_put(object_key)
    headers = storage.default_upload_headers().copy()
    if payload.content_type:
        headers["Content-Type"] = payload.content_type
    ticket = BrandAssetUploadResponse(
        data={
            "object_key": object_key,
            "upload_url": upload_url,
            "headers": headers,
            "kind": payload.kind,
        }
    )
    return ticket


@router.post(
    "/brand-kits/{brand_kit_id}/assets",
    response_model=BrandAssetResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))],
)
async def register_brand_asset(
    brand_kit_id: UUID,
    payload: BrandAssetCreate,
    repo: BrandKitRepository = Depends(get_brand_kit_repository),
    storage: MinioStorageService = Depends(get_storage_service),
    org_id: UUID = Depends(get_org_id),
) -> BrandAssetResponse:
    brand_kit = await repo.get(org_id, brand_kit_id)
    if brand_kit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")
    uri = payload.uri or storage.object_uri(payload.object_key)
    asset = await repo.create_asset(
        org_id=org_id,
        brand_kit_id=brand_kit_id,
        payload=BrandAssetCreate(
            label=payload.label,
            kind=payload.kind,
            object_key=payload.object_key,
            uri=uri,
        ),
    )
    return BrandAssetResponse(data=asset)


@router.get(
    "/brand-kits/{brand_kit_id}/assets",
    response_model=BrandAssetListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_brand_assets(
    brand_kit_id: UUID,
    repo: BrandKitRepository = Depends(get_brand_kit_repository),
    org_id: UUID = Depends(get_org_id),
) -> BrandAssetListResponse:
    brand_kit = await repo.get(org_id, brand_kit_id)
    if brand_kit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")
    assets = await repo.list_assets(org_id, brand_kit_id)
    return BrandAssetListResponse(data=assets)


@router.delete(
    "/brand-kits/{brand_kit_id}/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))],
)
async def delete_brand_asset(
    brand_kit_id: UUID,
    asset_id: UUID,
    repo: BrandKitRepository = Depends(get_brand_kit_repository),
    org_id: UUID = Depends(get_org_id),
) -> None:
    brand_kit = await repo.get(org_id, brand_kit_id)
    if brand_kit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")
    await repo.delete_asset(org_id, brand_kit_id, asset_id)
