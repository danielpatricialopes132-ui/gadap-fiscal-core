"""Endpoints REST para Gestão de Webhooks Transacionais para ERPs.

Rotas:
- POST /api/v1/fiscal/webhooks/subscriptions: Cadastra novo endpoint de webhook para uma empresa.
- GET  /api/v1/fiscal/webhooks/subscriptions/{empresa_id}: Lista webhooks cadastrados para o tenant.
- DELETE /api/v1/fiscal/webhooks/subscriptions/{subscription_id}: Desativa/remove um webhook.
- POST /api/v1/fiscal/webhooks/testar/{subscription_id}: Envia um ping/evento de teste assinado.
- POST /api/v1/fiscal/webhooks/reprocessar: Executa a fila de retentativas pendentes.
"""

from typing import Optional, List
import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.fiscal import Empresa
from app.models.webhook import WebhookSubscription, WebhookDelivery
from app.services.webhooks.dispatcher import WebhookDispatcher, EVENTOS_VALIDOS

router = APIRouter(prefix="/api/v1/fiscal/webhooks", tags=["Webhooks & Eventos Transacionais"])


class CriarWebhookSubscriptionInput(BaseModel):
    empresa_id: str = Field(..., description="ID da empresa cadastrada no GADAP Fiscal Core")
    url_endpoint: str = Field(..., description="URL HTTP/HTTPS do ERP que receberá os POSTs assinados")
    secret_key: Optional[str] = Field(
        None,
        description="Segredo para validação HMAC-SHA256 (gerado automaticamente se omitido)",
    )
    eventos_ativos: str = Field(
        default="*",
        description="Lista de eventos separados por vírgula ou '*' para todos",
        examples=["fiscal.nfe.autorizada,fiscal.nfe.rejeitada,fiscal.whatsapp.entregue"],
    )


class WebhookSubscriptionResponse(BaseModel):
    id: str
    empresa_id: str
    url_endpoint: str
    secret_key: str
    eventos_ativos: str
    is_active: bool
    created_at: str


class WebhookDeliveryResponse(BaseModel):
    id: str
    subscription_id: str
    evento: str
    response_status: Optional[int] = None
    attempts: int
    max_attempts: int
    next_retry_at: Optional[str] = None
    delivered_at: Optional[str] = None
    created_at: str


@router.post(
    "/subscriptions",
    response_model=WebhookSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra Endpoint de Webhook para o ERP",
    description="Permite que o ERP receba eventos em tempo real assinados via HMAC-SHA256 no cabeçalho X-GADAP-Signature.",
)
def criar_subscription(
    payload: CriarWebhookSubscriptionInput,
    db: Session = Depends(get_db_session),
) -> WebhookSubscriptionResponse:
    empresa = db.query(Empresa).filter(Empresa.id == payload.empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa {payload.empresa_id} não encontrada.",
        )

    secret = payload.secret_key or secrets.token_hex(32)

    sub_id = str(uuid.uuid4())
    nova_sub = WebhookSubscription(
        id=sub_id,
        empresa_id=payload.empresa_id,
        url_endpoint=payload.url_endpoint,
        secret_key=secret,
        eventos_ativos=payload.eventos_ativos,
        is_active=True,
    )
    db.add(nova_sub)
    db.commit()
    db.refresh(nova_sub)

    sub_final_id = nova_sub.id or sub_id
    created_iso = (nova_sub.created_at or datetime.now(timezone.utc)).isoformat()


    return WebhookSubscriptionResponse(
        id=sub_final_id,
        empresa_id=nova_sub.empresa_id,
        url_endpoint=nova_sub.url_endpoint,
        secret_key=nova_sub.secret_key,
        eventos_ativos=nova_sub.eventos_ativos,
        is_active=nova_sub.is_active,
        created_at=created_iso,
    )




@router.get(
    "/subscriptions/{empresa_id}",
    response_model=List[WebhookSubscriptionResponse],
    summary="Lista Webhooks Cadastrados para uma Empresa",
)
def listar_subscriptions(
    empresa_id: str,
    db: Session = Depends(get_db_session),
) -> List[WebhookSubscriptionResponse]:
    subs = db.query(WebhookSubscription).filter(WebhookSubscription.empresa_id == empresa_id).all()
    return [
        WebhookSubscriptionResponse(
            id=s.id,
            empresa_id=s.empresa_id,
            url_endpoint=s.url_endpoint,
            secret_key=s.secret_key,
            eventos_ativos=s.eventos_ativos,
            is_active=s.is_active,
            created_at=s.created_at.isoformat(),
        )
        for s in subs
    ]


@router.delete(
    "/subscriptions/{subscription_id}",
    summary="Remove ou Desativa Endpoint de Webhook",
)
def deletar_subscription(
    subscription_id: str,
    db: Session = Depends(get_db_session),
):
    sub = db.query(WebhookSubscription).filter(WebhookSubscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inscrição de webhook não encontrada.")
    db.delete(sub)
    db.commit()
    return {"sucesso": True, "mensagem": "Webhook removido com sucesso."}


@router.post(
    "/testar/{subscription_id}",
    summary="Dispara Evento de Teste Assinado (Ping / Test Event)",
)
def testar_webhook(
    subscription_id: str,
    db: Session = Depends(get_db_session),
):
    sub = db.query(WebhookSubscription).filter(WebhookSubscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inscrição de webhook não encontrada.")

    payload_teste = {
        "mensagem": "Ping de teste do GADAP Fiscal Hub",
        "ambiente": "homologacao",
        "hora": datetime.now(timezone.utc).isoformat(),
    }

    resultado = WebhookDispatcher.enviar_webhook(
        url_endpoint=sub.url_endpoint,
        secret_key=sub.secret_key,
        evento="fiscal.ping",
        payload_data=payload_teste,
    )
    return resultado


@router.post(
    "/reprocessar",
    summary="Reprocessa Entregas Pendentes na Fila com Backoff Exponencial",
)
def reprocessar_pendentes_endpoint(
    db: Session = Depends(get_db_session),
):
    qtd = WebhookDispatcher.reprocessar_retentativas_pendentes(db)
    return {"sucesso": True, "reprocessados": qtd}
