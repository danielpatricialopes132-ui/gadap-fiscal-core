"""Módulo de API v1 do GADAP Fiscal Core."""

from app.api.v1.endpoints.fiscal import router as fiscal_router

__all__ = ["fiscal_router"]
