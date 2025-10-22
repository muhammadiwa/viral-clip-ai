from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .db import init_db
from .api.routes.projects import router as projects_router
from .api.routes.videos import router as videos_router
from .api.routes.jobs import router as jobs_router
from .api.routes.clips import router as clips_router
from .api.routes.retells import router as retells_router
from .api.routes.artifacts import router as artifacts_router
from .api.routes.billing import router as billing_router
from .api.routes.users import router as users_router
from .api.routes.organizations import router as organizations_router
from .api.routes.auth import router as auth_router
from .api.routes.transcripts import router as transcripts_router
from .api.routes.audit import router as audit_router
from .api.routes.observability import router as observability_router
from .api.routes.dmca import router as dmca_router
from .api.routes.webhooks import router as webhooks_router
from .api.routes.branding import router as branding_router
from .telemetry import configure_tracing, setup_prometheus


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.project_name, version="0.1.0")

    allow_origins = settings.cors_origins or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in allow_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _startup() -> None:
        await init_db()

    @app.get("/healthz")
    def healthz() -> dict[str, str | bool]:
        return {"ok": True, "service": "api"}

    app.include_router(projects_router, prefix=settings.api_v1_prefix)
    app.include_router(videos_router, prefix=settings.api_v1_prefix)
    app.include_router(jobs_router, prefix=settings.api_v1_prefix)
    app.include_router(clips_router, prefix=settings.api_v1_prefix)
    app.include_router(retells_router, prefix=settings.api_v1_prefix)
    app.include_router(transcripts_router, prefix=settings.api_v1_prefix)
    app.include_router(artifacts_router, prefix=settings.api_v1_prefix)
    app.include_router(billing_router, prefix=settings.api_v1_prefix)
    app.include_router(users_router, prefix=settings.api_v1_prefix)
    app.include_router(organizations_router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(audit_router, prefix=settings.api_v1_prefix)
    app.include_router(observability_router, prefix=settings.api_v1_prefix)
    app.include_router(dmca_router, prefix=settings.api_v1_prefix)
    app.include_router(webhooks_router, prefix=settings.api_v1_prefix)
    app.include_router(branding_router, prefix=settings.api_v1_prefix)

    if settings.enable_prometheus_metrics:
        setup_prometheus(app)
    configure_tracing(app)

    return app


app = create_app()
