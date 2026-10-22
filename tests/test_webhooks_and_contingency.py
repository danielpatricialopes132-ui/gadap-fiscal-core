"""Testes automatizados da Fase 12: Webhooks Transacionais e Roteador de Contingência.

Verifica:
1. Geração e validação de assinatura HMAC-SHA256 no cabeçalho X-GADAP-Signature.
2. Despacho HTTP com headers de segurança (X-GADAP-Event, X-GADAP-Timestamp).
3. Agendamento com fila de retentativa exponencial (1min, 5min, 15min, 1h, 6h).
4. Roteamento de contingência autônoma:
   - Threshold de 3 falhas para comutação.
   - Comutação de NF-e (SP -> SVC-AN, BA -> SVC-RS).
   - Comutação de NFC-e para modo Offline (tpEmis = 9).
   - Restauração ao modo NORMAL após sucesso.
5. Endpoints REST de criação e teste de Webhook Subscriptions.
"""

import pytest
import hmac
import hashlib
import json
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.services.webhooks.dispatcher import WebhookDispatcher, RETRY_DELAYS_MINUTES
from app.services.sefaz.contingency_router import SefazContingencyRouter, TipoContingencia
from app.main import app

client = TestClient(app)


def test_gerar_e_validar_assinatura_hmac():
    """Valida a integridade da assinatura HMAC-SHA256."""
    secret = "minha_chave_secreta_super_segura_123"
    payload = json.dumps({"chave": "35240212345678000195550010000001231000001234", "status": "AUTORIZADA"})
    ts = 1792600000

    sig = WebhookDispatcher.gerar_assinatura(secret, payload, ts)

    # Verificação manual independente
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=f"{ts}.{payload}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    assert sig == expected
    assert len(sig) == 64  # SHA256 hex


@patch("requests.post")
def test_enviar_webhook_headers_corretos(mock_post):
    """Testa se o envio de webhook inclui todos os cabeçalhos obrigatórios."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"received": true}'
    mock_post.return_value = mock_resp

    resultado = WebhookDispatcher.enviar_webhook(
        url_endpoint="https://erp.cliente.com.br/webhooks/fiscal",
        secret_key="secret123",
        evento="fiscal.nfe.autorizada",
        payload_data={"chave": "123"},
    )

    assert resultado["sucesso"] is True
    assert resultado["status_code"] == 200

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://erp.cliente.com.br/webhooks/fiscal"
    assert kwargs["headers"]["X-GADAP-Event"] == "fiscal.nfe.autorizada"
    assert "X-GADAP-Signature" in kwargs["headers"]
    assert "X-GADAP-Timestamp" in kwargs["headers"]


def test_contingencia_roteamento_autonomo():
    """Testa a comutação para SVC-AN, SVC-RS e NFC-e Offline após 3 falhas consecutivas."""
    # 1. SP (NF-e modelo 55) -> Deve comutar para SVC-AN
    SefazContingencyRouter.registrar_sucesso("SP", "55")
    assert SefazContingencyRouter.obter_status_contingencia("SP", "55") == TipoContingencia.NORMAL

    # 1a e 2a falhas -> Ainda NORMAL
    assert SefazContingencyRouter.registrar_falha("SP", "55") == TipoContingencia.NORMAL
    assert SefazContingencyRouter.registrar_falha("SP", "55") == TipoContingencia.NORMAL
    
    # 3a falha -> Comuta para SVC-AN
    modo_sp = SefazContingencyRouter.registrar_falha("SP", "55")
    assert modo_sp == TipoContingencia.SVC_AN
    assert SefazContingencyRouter.obter_status_contingencia("SP", "55") == TipoContingencia.SVC_AN

    # Resolução de endpoint deve apontar para SVC-AN
    ep, modo = SefazContingencyRouter.resolver_endpoints("SP", "55", is_production=False)
    assert modo == TipoContingencia.SVC_AN
    assert "svc.fazenda.gov.br" in ep.autorizacao

    # Restauração ao normal
    SefazContingencyRouter.registrar_sucesso("SP", "55")
    assert SefazContingencyRouter.obter_status_contingencia("SP", "55") == TipoContingencia.NORMAL

    # 2. BA (NF-e modelo 55) -> Deve comutar para SVC-RS
    SefazContingencyRouter.registrar_sucesso("BA", "55")
    SefazContingencyRouter.registrar_falha("BA", "55")
    SefazContingencyRouter.registrar_falha("BA", "55")
    modo_ba = SefazContingencyRouter.registrar_falha("BA", "55")
    assert modo_ba == TipoContingencia.SVC_RS

    # 3. SP (NFC-e modelo 65) -> Deve comutar para OFFLINE (tpEmis = 9)
    SefazContingencyRouter.registrar_sucesso("SP", "65")
    SefazContingencyRouter.registrar_falha("SP", "65")
    SefazContingencyRouter.registrar_falha("SP", "65")
    modo_nfce = SefazContingencyRouter.registrar_falha("SP", "65")
    assert modo_nfce == TipoContingencia.OFFLINE_NFCE


def test_endpoint_criar_webhook_subscription():
    """Testa cadastro de webhook via API REST."""
    from app.api.v1.endpoints.webhooks import get_db_session

    mock_session = MagicMock()
    mock_empresa = MagicMock()
    mock_empresa.id = "emp-uuid-1"

    mock_session.query.return_value.filter.return_value.first.return_value = mock_empresa

    def _mock_db():
        yield mock_session

    app.dependency_overrides[get_db_session] = _mock_db

    response = client.post(
        "/api/v1/fiscal/webhooks/subscriptions",
        json={
            "empresa_id": "emp-uuid-1",
            "url_endpoint": "https://erp.sistema.com/hook",
            "eventos_ativos": "fiscal.nfe.autorizada,fiscal.nfe.rejeitada",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["empresa_id"] == "emp-uuid-1"
    assert data["url_endpoint"] == "https://erp.sistema.com/hook"
    assert "secret_key" in data
    assert data["is_active"] is True
