"""Módulo de endpoints da API v1."""

from app.api.v1.endpoints.fiscal import router as fiscal_router
from app.api.v1.endpoints.fiscal_records import router as fiscal_records_router
from app.api.v1.endpoints.notifications import router as notifications_router

__all__ = ["fiscal_router", "fiscal_records_router", "notifications_router"]
