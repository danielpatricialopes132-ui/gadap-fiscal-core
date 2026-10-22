"""Modelos relacionais para o Sistema de Webhooks Transacionais para ERPs.

Tabelas:
- webhook_subscriptions: endpoints HTTP cadastrados por cada tenant/empresa e chaves secretas.
- webhook_deliveries: histórico de entregas, payloads, status code e retentativas com backoff exponencial.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class WebhookSubscription(Base):
    """Endpoints cadastrados pelos ERPs clientes para receber eventos fiscais."""
    __tablename__ = "webhook_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    empresa_id = Column(String(36), ForeignKey("empresas.id"), nullable=False, index=True)
    url_endpoint = Column(Text, nullable=False)
    secret_key = Column(String(128), nullable=False)  # Segredo para assinatura HMAC-SHA256
    
    # Eventos ativos separados por vírgula ou JSON (ex: "fiscal.nfe.autorizada,fiscal.nfe.rejeitada")
    eventos_ativos = Column(Text, nullable=False, default="*")
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", backref="webhook_subscriptions")
    deliveries = relationship("WebhookDelivery", back_populates="subscription", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    """Registro e auditoria de cada disparo de webhook com fila de retentativa."""
    __tablename__ = "webhook_deliveries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id = Column(String(36), ForeignKey("webhook_subscriptions.id"), nullable=False, index=True)
    evento = Column(String(50), nullable=False, index=True)
    payload = Column(Text, nullable=False)  # JSON serializado
    
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    
    # Próxima tentativa e data de entrega com sucesso
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    subscription = relationship("WebhookSubscription", back_populates="deliveries")

    __table_args__ = (
        Index("idx_delivery_pending", "response_status", "attempts", "next_retry_at"),
    )
