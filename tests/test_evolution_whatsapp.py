"""Testes automatizados da integração com a Evolution API (WhatsApp).

Verifica:
1. Sanitização de números de telefone para padrão E.164 brasileiro (55 + DDD + 8/9 dígitos).
2. Formatação correta de cabeçalhos de autenticação (apikey).
3. Chamada de envio de mensagem de texto (POST /message/sendText/{instance}).
4. Chamada de envio de mídia PDF com legenda (POST /message/sendMedia/{instance}).
5. Fluxo completo de notificação de nota fiscal autorizada.
6. Endpoint REST de reenvio avulso de WhatsApp (/api/v1/fiscal/documentos/{chave}/reenviar-whatsapp).
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.services.notifications.evolution_whatsapp import EvolutionWhatsAppClient
from app.main import app

client = TestClient(app)


def test_sanitizar_numero_telefone():
    """Valida a sanitização e normalização de telefones celulares brasileiros."""
    # Com DDD e hífen/espaços
    assert EvolutionWhatsAppClient.sanitizar_numero("(11) 99999-8888") == "5511999998888"
    assert EvolutionWhatsAppClient.sanitizar_numero("11999998888") == "5511999998888"
    assert EvolutionWhatsAppClient.sanitizar_numero("+55 11 99999-8888") == "5511999998888"
    assert EvolutionWhatsAppClient.sanitizar_numero("5511999998888") == "5511999998888"

    # Fixo / 10 dígitos (DDD + 8 dígitos)
    assert EvolutionWhatsAppClient.sanitizar_numero("(11) 3333-4444") == "551133334444"
    assert EvolutionWhatsAppClient.sanitizar_numero("1133334444") == "551133334444"

    # String vazia deve levantar exceção
    with pytest.raises(ValueError):
        EvolutionWhatsAppClient.sanitizar_numero("")


@patch("requests.post")
def test_enviar_mensagem_texto(mock_post):
    """Testa envio de texto verificando headers, url e payload json."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"key": {"id": "EVO_MSG_12345"}}'
    mock_response.json.return_value = {"key": {"id": "EVO_MSG_12345"}}
    mock_post.return_value = mock_response

    wp = EvolutionWhatsAppClient(
        base_url="https://whatsapp-ecostone.onrender.com",
        api_key="Gabriel2006!",
        instance="ecostone",
    )

    resultado = wp.enviar_mensagem_texto("11999998888", "Mensagem de teste SEFAZ")

    assert resultado["sucesso"] is True
    assert resultado["message_id"] == "EVO_MSG_12345"

    mock_post.assert_called_once()
    called_args, called_kwargs = mock_post.call_args

    assert called_args[0] == "https://whatsapp-ecostone.onrender.com/message/sendText/ecostone"
    assert called_kwargs["headers"]["apikey"] == "Gabriel2006!"
    assert called_kwargs["headers"]["Content-Type"] == "application/json"
    assert called_kwargs["json"]["number"] == "5511999998888"
    assert called_kwargs["json"]["text"] == "Mensagem de teste SEFAZ"


@patch("requests.post")
def test_enviar_documento_pdf(mock_post):
    """Testa envio de documento PDF através do endpoint sendMedia."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = '{"key": {"id": "EVO_PDF_99999"}}'
    mock_response.json.return_value = {"key": {"id": "EVO_PDF_99999"}}
    mock_post.return_value = mock_response

    wp = EvolutionWhatsAppClient(
        base_url="https://whatsapp-ecostone.onrender.com",
        api_key="Gabriel2006!",
        instance="ecostone",
    )

    pdf_url = "https://ogpqsslzbocrncusauzl.supabase.co/storage/v1/object/sign/danfe.pdf"
    resultado = wp.enviar_documento_pdf(
        telefone="11988887777",
        pdf_url=pdf_url,
        nome_arquivo="DANFE_123.pdf",
        legenda="Segue o DANFE da sua nota",
    )

    assert resultado["sucesso"] is True
    assert resultado["message_id"] == "EVO_PDF_99999"

    mock_post.assert_called_once()
    called_args, called_kwargs = mock_post.call_args

    assert called_args[0] == "https://whatsapp-ecostone.onrender.com/message/sendMedia/ecostone"
    assert called_kwargs["headers"]["apikey"] == "Gabriel2006!"
    assert called_kwargs["json"]["number"] == "5511988887777"
    assert called_kwargs["json"]["mediatype"] == "document"
    assert called_kwargs["json"]["media"] == pdf_url
    assert called_kwargs["json"]["caption"] == "Segue o DANFE da sua nota"



@patch("requests.post")
def test_enviar_notificacao_nota_autorizada(mock_post):
    """Testa o método completo de notificação amigável com DANFE."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"key": {"id": "EVO_FULL_888"}}'
    mock_response.json.return_value = {"key": {"id": "EVO_FULL_888"}}
    mock_post.return_value = mock_response

    wp = EvolutionWhatsAppClient()
    res = wp.enviar_notificacao_nota_autorizada(
        chave_acesso="35240212345678000195550010000001231000001234",
        numero_nota=123,
        destinatario_nome="Supermercado Silva",
        telefone="11999998888",
        pdf_url="https://fake-storage.com/danfe.pdf",
        razao_social_emitente="ECOSTONE LTDA",
    )

    assert res["sucesso"] is True
    assert res["message_id"] == "EVO_FULL_888"

    payload_enviado = mock_post.call_args[1]["json"]
    legenda = payload_enviado["caption"]
    assert "Supermercado Silva" in legenda
    assert "123" in legenda
    assert "35240212345678000195550010000001231000001234" in legenda
    assert "ECOSTONE LTDA" in legenda



@patch("app.services.notifications.evolution_whatsapp.EvolutionWhatsAppClient.enviar_notificacao_nota_autorizada")
@patch("app.services.storage.supabase_storage.SupabaseStorageService.obter_url_download_temporaria")
def test_endpoint_reenviar_whatsapp(mock_storage_url, mock_enviar_wp):
    """Testa a rota POST /api/v1/fiscal/documentos/{chave}/reenviar-whatsapp."""
    mock_storage_url.return_value = "https://storage.supabase.com/danfe.pdf"
    mock_enviar_wp.return_value = {"sucesso": True, "message_id": "MSG_REENVIO_123"}

    # Mock DB query
    from app.api.v1.endpoints.notifications import get_db_session

    mock_session = MagicMock()
    mock_doc = MagicMock()
    mock_doc.chave_acesso = "35240212345678000195550010000001231000001234"
    mock_doc.status = "AUTORIZADA"
    mock_doc.numero = 123
    mock_doc.destinatario_nome = "Cliente Teste"
    mock_doc.arquivos = []
    mock_doc.empresa = MagicMock()
    mock_doc.empresa.razao_social = "Emitente Teste LTDA"

    mock_session.query.return_value.filter.return_value.first.return_value = mock_doc

    def _mock_db_generator():
        yield mock_session

    app.dependency_overrides[get_db_session] = _mock_db_generator

    response = client.post(
        "/api/v1/fiscal/documentos/35240212345678000195550010000001231000001234/reenviar-whatsapp",
        json={"telefone": "11988887777", "destinatario_nome": "Cliente VIP"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["sucesso"] is True
    assert data["chave_acesso"] == "35240212345678000195550010000001231000001234"
    assert data["telefone_destino"] == "5511988887777"
    assert data["message_id"] == "MSG_REENVIO_123"
