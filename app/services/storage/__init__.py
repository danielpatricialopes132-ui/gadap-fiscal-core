"""Módulo unificado de storage do GADAP Fiscal Core."""

from app.services.storage.supabase_storage import SupabaseStorageService
from app.services.storage.local_storage import FiscalStorageService

__all__ = ["SupabaseStorageService", "FiscalStorageService"]
