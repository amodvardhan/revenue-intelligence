"""FastAPI application entry — routers and middleware."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.dimensions import router as dimensions_router
from app.api.v1.health import router as health_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.query import router as query_router
from app.api.v1.revenue import router as revenue_router
from app.api.v1.semantic_layer import router as semantic_layer_router
from app.api.v1.hubspot import router as hubspot_router
from app.api.v1.tenant_settings import router as tenant_settings_router
from app.api.v1.fx_routes import router as fx_rates_router
from app.api.v1.forecast_routes import router as forecast_router
from app.api.v1.costs_routes import router as costs_router
from app.api.v1.segments_routes import router as segments_router
from app.api.v1.ingest_phase5 import router as ingest_phase5_router
from app.api.v1.phase6_governance import router as phase6_governance_router
from app.api.v1.phase6_sso import router as phase6_sso_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Revenue Intelligence Platform",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(dimensions_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(revenue_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(query_router, prefix="/api/v1")
    app.include_router(semantic_layer_router, prefix="/api/v1")
    app.include_router(hubspot_router, prefix="/api/v1")
    app.include_router(tenant_settings_router, prefix="/api/v1")
    app.include_router(fx_rates_router, prefix="/api/v1")
    app.include_router(forecast_router, prefix="/api/v1")
    app.include_router(costs_router, prefix="/api/v1")
    app.include_router(segments_router, prefix="/api/v1")
    app.include_router(ingest_phase5_router, prefix="/api/v1")
    app.include_router(phase6_sso_router, prefix="/api/v1")
    app.include_router(phase6_governance_router, prefix="/api/v1")
    return app


app = create_app()
