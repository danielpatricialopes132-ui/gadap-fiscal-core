"""Dispatcher Assíncrono de Webhooks Transacionais para ERPs.

Funcionalidades:
1. Despacho HTTP com assinatura HMAC-SHA256 no cabeçalho `X-GADAP-Signature`.
2. Cabeçalho de timestamp `X-GADAP-Timestamp` para prevenção de replay attacks.
3. Eventos fiscais suportados:
   - fiscal.nfe.autorizada
   - fiscal.nfe.rejeitada
   - fiscal.nfe.cancelada
   - fiscal.cce.homologada
   - fiscal.whatsapp.entregue
   - fiscal.sefaz.oscilacao
4. Política de retentativa exponencial (5 tentativas):
   - Tentativa 1: +1 minuto
   - Tentativa 2: +5 minutos
   - Tentativa 3: +15 minutos
   - Tentativa 4: +1 hora
   - Tentativa 5: +6 horas
"""

from typing import Optional, Dict, Any, List
import hmac
import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
import logging
import requests
from sqlalchemy.orm import Session

from app.models.webhook import WebhookSubscription, WebhookDelivery
from app.db.session import get_engine

logger = logging.getLogger("gadap.webhooks")

# Intervalos de retentativa exponencial por tentativa realizada (0 a 4)
RETRY_DELAYS_MINUTES = [1, 5, 15, 60, 360]

EVENTOS_VALIDOS = {
    "fiscal.nfe.autorizada",
    "fiscal.nfe.rejeitada",
    "fiscal.nfe.cancelada",
    "fiscal.cce.homologada",
    "fiscal.whatsapp.entregue",
    "fiscal.sefaz.oscilacao",
}


class WebhookDispatcher:
    """Motor de despacho, assinatura e retentativa de Webhooks para sistemas ERP."""

    @classmethod
    def gerar_assinatura(cls, secret_key: str, payload_json: str, timestamp: int) -> str:
        """Gera assinatura HMAC-SHA256 sobre 'timestamp.payload'."""
        data_to_sign = f"{timestamp}.{payload_json}".encode("utf-8")
        signature = hmac.new(
            key=secret_key.encode("utf-8"),
            msg=data_to_sign,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return signature

    @classmethod
    def enviar_webhook(
        cls,
        url_endpoint: str,
        secret_key: str,
        evento: str,
        payload_data: Dict[str, Any],
        timeout: int = 10,
    ) -> Dict[str, Any]:
        """Efetua a requisição HTTP POST ao endpoint do ERP com cabeçalhos de segurança."""
        now_ts = int(time.time())
        corpo = {
            "event": evento,
            "timestamp": now_ts,
            "data": payload_data,
        }
        payload_json = json.dumps(corpo, ensure_ascii=False)
        assinatura = cls.gerar_assinatura(secret_key, payload_json, now_ts)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "GADAP-Fiscal-Webhook-Dispatcher/1.0",
            "X-GADAP-Event": evento,
            "X-GADAP-Timestamp": str(now_ts),
            "X-GADAP-Signature": assinatura,
        }

        try:
            logger.info(f"Disparando webhook {evento} para {url_endpoint}...")
            resp = requests.post(url_endpoint, data=payload_json, headers=headers, timeout=timeout)
            sucesso = 200 <= resp.status_code < 300
            return {
                "sucesso": sucesso,
                "status_code": resp.status_code,
                "response_body": resp.text[:1000] if resp.text else "",
                "payload_enviado": payload_json,
            }
        except Exception as e:
            logger.warning(f"Falha de conexão no webhook {url_endpoint}: {e}")
            return {
                "sucesso": False,
                "status_code": None,
                "response_body": str(e),
                "payload_enviado": payload_json,
            }

    @classmethod
    def disparar_evento(
        cls,
        db: Session,
        empresa_id: str,
        evento: str,
        payload_data: Dict[str, Any],
    ) -> List[str]:
        """Localiza as inscrições ativas da empresa e dispara os webhooks, registrando histórico."""
        subscriptions = (
            db.query(WebhookSubscription)
            .filter(
                WebhookSubscription.empresa_id == empresa_id,
                WebhookSubscription.is_active.is_(True),
            )
            .all()
        )

        delivery_ids = []
        for sub in subscriptions:
            # Verifica se o evento está inscrito
            eventos_sub = [e.strip() for e in sub.eventos_ativos.split(",")]
            if "*" not in eventos_sub and evento not in eventos_sub:
                continue

            # Envio imediato
            resultado = cls.enviar_webhook(
                url_endpoint=sub.url_endpoint,
                secret_key=sub.secret_key,
                evento=evento,
                payload_data=payload_data,
            )

            now = datetime.now(timezone.utc)
            attempts = 1
            sucesso = resultado["sucesso"]
            
            next_retry = None
            delivered_at = now if sucesso else None

            if not sucesso:
                # Agendamento da primeira retentativa exponencial (+1 minuto)
                delay_minutes = RETRY_DELAYS_MINUTES[0]
                next_retry = now + timedelta(minutes=delay_minutes)
                logger.info(f"Webhook {sub.id} falhou. Reagendado para {next_retry.isoformat()}.")

            delivery = WebhookDelivery(
                subscription_id=sub.id,
                evento=evento,
                payload=resultado["payload_enviado"],
                response_status=resultado["status_code"],
                response_body=resultado["response_body"],
                attempts=attempts,
                max_attempts=len(RETRY_DELAYS_MINUTES),
                next_retry_at=next_retry,
                delivered_at=delivered_at,
            )
            db.add(delivery)
            db.flush()
            delivery_ids.append(delivery.id)

        db.commit()
        return delivery_ids

    @classmethod
    def reprocessar_retentativas_pendentes(cls, db: Session) -> int:
        """Processa as entregas pendentes cujo next_retry_at já expirou."""
        now = datetime.now(timezone.utc)
        pendentes = (
            db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.delivered_at.is_(None),
                WebhookDelivery.attempts < WebhookDelivery.max_attempts,
                WebhookDelivery.next_retry_at <= now,
            )
            .all()
        )

        reprocessadas = 0
        for deliv in pendentes:
            sub = deliv.subscription
            if not sub or not sub.is_active:
                continue

            try:
                corpo = json.loads(deliv.payload)
                data_dict = corpo.get("data", {})
            except Exception:
                data_dict = {}

            resultado = cls.enviar_webhook(
                url_endpoint=sub.url_endpoint,
                secret_key=sub.secret_key,
                evento=deliv.evento,
                payload_data=data_dict,
            )

            deliv.attempts += 1
            deliv.response_status = resultado["status_code"]
            deliv.response_body = resultado["response_body"]

            if resultado["sucesso"]:
                deliv.delivered_at = datetime.now(timezone.utc)
                deliv.next_retry_at = None
                logger.info(f"Webhook delivery {deliv.id} entregue com sucesso na tentativa {deliv.attempts}!")
            else:
                if deliv.attempts < deliv.max_attempts:
                    idx = min(deliv.attempts, len(RETRY_DELAYS_MINUTES) - 1)
                    prox_delay = RETRY_DELAYS_MINUTES[idx]
                    deliv.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=prox_delay)
                else:
                    deliv.next_retry_at = None
                    logger.error(f"Webhook delivery {deliv.id} esgotou todas as {deliv.max_attempts} tentativas.")

            reprocessadas += 1

        db.commit()
        return reprocessadas
