from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.webhooks import (
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEndpointCreate,
    WebhookEndpointUpdate,
    WebhookEventType,
)
from ..models.webhook import WebhookDeliveryModel, WebhookEndpointModel


class WebhookEndpointsRepository(Protocol):
    async def create_endpoint(
        self, *, org_id: UUID, payload: WebhookEndpointCreate
    ) -> WebhookEndpoint: ...

    async def list_endpoints(self, *, org_id: UUID) -> list[WebhookEndpoint]: ...

    async def get_endpoint(
        self, *, endpoint_id: UUID, org_id: UUID
    ) -> WebhookEndpoint | None: ...

    async def update_endpoint(
        self,
        *,
        endpoint_id: UUID,
        org_id: UUID,
        payload: WebhookEndpointUpdate,
    ) -> WebhookEndpoint | None: ...

    async def publish_event(
        self,
        *,
        org_id: UUID,
        event_type: WebhookEventType,
        payload: dict,
    ) -> list[WebhookDelivery]: ...

    async def list_deliveries(
        self,
        *,
        org_id: UUID,
        endpoint_id: UUID | None = None,
        status: WebhookDeliveryStatus | None = None,
    ) -> list[WebhookDelivery]: ...

    async def update_delivery(
        self,
        *,
        delivery_id: UUID,
        org_id: UUID,
        status: WebhookDeliveryStatus,
        response_code: int | None,
        error_message: str | None,
    ) -> WebhookDelivery | None: ...


class InMemoryWebhookEndpointsRepository:
    """In-memory repository tracking webhook configuration and delivery logs."""

    def __init__(self) -> None:
        self._endpoints_by_org: dict[UUID, dict[UUID, WebhookEndpoint]] = defaultdict(dict)
        self._deliveries_by_org: dict[UUID, dict[UUID, WebhookDelivery]] = defaultdict(dict)

    async def create_endpoint(
        self, *, org_id: UUID, payload: WebhookEndpointCreate
    ) -> WebhookEndpoint:
        endpoint = WebhookEndpoint(
            org_id=org_id, **payload.model_dump(exclude_none=True)
        )
        self._endpoints_by_org[org_id][endpoint.id] = endpoint
        return endpoint

    async def list_endpoints(self, *, org_id: UUID) -> list[WebhookEndpoint]:
        endpoints = list(self._endpoints_by_org.get(org_id, {}).values())
        endpoints.sort(key=lambda endpoint: endpoint.created_at, reverse=True)
        return endpoints

    async def get_endpoint(
        self, *, endpoint_id: UUID, org_id: UUID
    ) -> WebhookEndpoint | None:
        return self._endpoints_by_org.get(org_id, {}).get(endpoint_id)

    async def update_endpoint(
        self,
        *,
        endpoint_id: UUID,
        org_id: UUID,
        payload: WebhookEndpointUpdate,
    ) -> WebhookEndpoint | None:
        endpoint = await self.get_endpoint(endpoint_id=endpoint_id, org_id=org_id)
        if endpoint is None:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        updated = endpoint.model_copy(
            update={
                **update_data,
                "updated_at": datetime.utcnow(),
            }
        )
        self._endpoints_by_org[org_id][endpoint_id] = updated
        return updated

    async def publish_event(
        self,
        *,
        org_id: UUID,
        event_type: WebhookEventType,
        payload: dict,
    ) -> list[WebhookDelivery]:
        endpoints = [
            endpoint
            for endpoint in self._endpoints_by_org.get(org_id, {}).values()
            if endpoint.is_active and event_type in endpoint.events
        ]
        deliveries: list[WebhookDelivery] = []
        for endpoint in endpoints:
            delivery = WebhookDelivery(
                org_id=org_id,
                endpoint_id=endpoint.id,
                event_type=event_type,
                payload=payload,
            )
            self._deliveries_by_org[org_id][delivery.id] = delivery
            deliveries.append(delivery)
        return deliveries

    async def list_deliveries(
        self,
        *,
        org_id: UUID,
        endpoint_id: UUID | None = None,
        status: WebhookDeliveryStatus | None = None,
    ) -> list[WebhookDelivery]:
        deliveries = list(self._deliveries_by_org.get(org_id, {}).values())
        if endpoint_id is not None:
            deliveries = [
                delivery for delivery in deliveries if delivery.endpoint_id == endpoint_id
            ]
        if status is not None:
            deliveries = [delivery for delivery in deliveries if delivery.status == status]
        deliveries.sort(key=lambda delivery: delivery.created_at, reverse=True)
        return deliveries

    async def update_delivery(
        self,
        *,
        delivery_id: UUID,
        org_id: UUID,
        status: WebhookDeliveryStatus,
        response_code: int | None,
        error_message: str | None,
    ) -> WebhookDelivery | None:
        delivery = self._deliveries_by_org.get(org_id, {}).get(delivery_id)
        if delivery is None:
            return None
        updated = delivery.model_copy(
            update={
                "status": status,
                "response_code": response_code,
                "error_message": error_message,
                "updated_at": datetime.utcnow(),
                "delivered_at": datetime.utcnow()
                if status == WebhookDeliveryStatus.SUCCEEDED
                else delivery.delivered_at,
            }
        )
        self._deliveries_by_org[org_id][delivery_id] = updated
        return updated


class SqlAlchemyWebhookEndpointsRepository(WebhookEndpointsRepository):
    """SQL-backed webhook configuration and delivery repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _model_to_endpoint(model: WebhookEndpointModel) -> WebhookEndpoint:
        return WebhookEndpoint(
            id=model.id,
            org_id=model.org_id,
            name=model.name,
            url=model.url,
            events=[WebhookEventType(event) for event in model.events],
            secret=model.secret,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _model_to_delivery(model: WebhookDeliveryModel) -> WebhookDelivery:
        return WebhookDelivery(
            id=model.id,
            org_id=model.org_id,
            endpoint_id=model.endpoint_id,
            event_type=WebhookEventType(model.event_type),
            payload=model.payload,
            status=WebhookDeliveryStatus(model.status),
            response_code=model.response_code,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            delivered_at=model.delivered_at,
        )

    async def create_endpoint(
        self, *, org_id: UUID, payload: WebhookEndpointCreate
    ) -> WebhookEndpoint:
        endpoint = WebhookEndpoint(
            org_id=org_id, **payload.model_dump(exclude_none=True)
        )
        model = WebhookEndpointModel(
            id=endpoint.id,
            org_id=endpoint.org_id,
            name=endpoint.name,
            url=str(endpoint.url),
            events=[event.value for event in endpoint.events],
            secret=endpoint.secret,
            is_active=endpoint.is_active,
            created_at=endpoint.created_at,
            updated_at=endpoint.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return endpoint

    async def list_endpoints(self, *, org_id: UUID) -> list[WebhookEndpoint]:
        result = await self._session.execute(
            select(WebhookEndpointModel)
            .where(WebhookEndpointModel.org_id == org_id)
            .order_by(WebhookEndpointModel.created_at.desc())
        )
        return [self._model_to_endpoint(row) for row in result.scalars().all()]

    async def get_endpoint(
        self, *, endpoint_id: UUID, org_id: UUID
    ) -> WebhookEndpoint | None:
        result = await self._session.execute(
            select(WebhookEndpointModel).where(
                WebhookEndpointModel.id == endpoint_id,
                WebhookEndpointModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._model_to_endpoint(model)

    async def update_endpoint(
        self,
        *,
        endpoint_id: UUID,
        org_id: UUID,
        payload: WebhookEndpointUpdate,
    ) -> WebhookEndpoint | None:
        result = await self._session.execute(
            select(WebhookEndpointModel).where(
                WebhookEndpointModel.id == endpoint_id,
                WebhookEndpointModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data:
            model.name = update_data["name"]
        if "url" in update_data and update_data["url"] is not None:
            model.url = str(update_data["url"])
        if "events" in update_data and update_data["events"] is not None:
            model.events = [event.value for event in update_data["events"]]
        if "is_active" in update_data:
            model.is_active = update_data["is_active"]
        if "secret" in update_data and update_data["secret"] is not None:
            model.secret = update_data["secret"]
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._model_to_endpoint(model)

    async def publish_event(
        self,
        *,
        org_id: UUID,
        event_type: WebhookEventType,
        payload: dict,
    ) -> list[WebhookDelivery]:
        endpoints = await self.list_endpoints(org_id=org_id)
        deliveries: list[WebhookDelivery] = []
        for endpoint in endpoints:
            if not endpoint.is_active or event_type not in endpoint.events:
                continue
            delivery = WebhookDelivery(
                org_id=org_id,
                endpoint_id=endpoint.id,
                event_type=event_type,
                payload=payload,
            )
            model = WebhookDeliveryModel(
                id=delivery.id,
                org_id=delivery.org_id,
                endpoint_id=delivery.endpoint_id,
                event_type=delivery.event_type.value,
                payload=delivery.payload,
                status=delivery.status.value,
                created_at=delivery.created_at,
                updated_at=delivery.updated_at,
            )
            self._session.add(model)
            deliveries.append(delivery)
        if deliveries:
            await self._session.flush()
            await self._session.commit()
        return deliveries

    async def list_deliveries(
        self,
        *,
        org_id: UUID,
        endpoint_id: UUID | None = None,
        status: WebhookDeliveryStatus | None = None,
    ) -> list[WebhookDelivery]:
        query = select(WebhookDeliveryModel).where(
            WebhookDeliveryModel.org_id == org_id
        )
        if endpoint_id is not None:
            query = query.where(WebhookDeliveryModel.endpoint_id == endpoint_id)
        if status is not None:
            query = query.where(WebhookDeliveryModel.status == status.value)
        query = query.order_by(WebhookDeliveryModel.created_at.desc())
        result = await self._session.execute(query)
        return [self._model_to_delivery(row) for row in result.scalars().all()]

    async def update_delivery(
        self,
        *,
        delivery_id: UUID,
        org_id: UUID,
        status: WebhookDeliveryStatus,
        response_code: int | None,
        error_message: str | None,
    ) -> WebhookDelivery | None:
        result = await self._session.execute(
            select(WebhookDeliveryModel).where(
                WebhookDeliveryModel.id == delivery_id,
                WebhookDeliveryModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        model.status = status.value
        model.response_code = response_code
        model.error_message = error_message
        model.updated_at = datetime.utcnow()
        if status == WebhookDeliveryStatus.SUCCEEDED:
            model.delivered_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._model_to_delivery(model)

