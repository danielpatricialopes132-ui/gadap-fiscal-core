"""Testes automatizados da Fase 10: Inbound DF-e e Manifestação do Destinatário (MDe).

Verifica:
1. Construção do XML distDFeInt v1.01 (busca por ultNSU e consChNFe).
2. Descompactação e parsing de nós docZip (resNFe e procNFe).
3. Construção e validação do XML de evento de Manifestação (Ciência, Confirmação, Não Realizada).
4. Endpoint POST /api/v1/fiscal/inbound/sincronizar/{empresa_id}.
5. Endpoint POST /api/v1/fiscal/inbound/{chave}/manifestar.
"""

import pytest
import gzip
import base64
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.services.sefaz.distribuicao_dfe import SefazDistribuicaoDFeService
from app.services.sefaz.manifestacao_destinatario import (
    SefazManifestacaoDestinatarioService,
    TP_CIENCIA,
    TP_CONFIRMACAO,
    TP_NAO_REALIZADA,
)
from app.main import app

client = TestClient(app)


def test_build_dist_dfe_xml():
    """Valida a montagem do XML de consulta sequencial ou pontual."""
    xml_nsu = SefazDistribuicaoDFeService.build_dist_dfe_xml(
        cnpj="12.345.678/0001-95",
        ult_nsu="15",
        tp_amb=2,
    )
    assert "<distDFeInt" in xml_nsu
    assert "<CNPJ>12345678000195</CNPJ>" in xml_nsu
    assert "<ultNSU>000000000000015</ultNSU>" in xml_nsu

    xml_ch = SefazDistribuicaoDFeService.build_dist_dfe_xml(
        cnpj="12.345.678/0001-95",
        ch_nfe="35240212345678000195550010000001231000001234",
    )
    assert "<consChNFe>" in xml_ch
    assert "<chNFe>35240212345678000195550010000001231000001234</chNFe>" in xml_ch


def test_decompress_gzip_and_parse():
    """Testa a descompressão em memória de um XML compactado simulando o retorno da SEFAZ."""
    xml_original = (
        '<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">\n'
        '  <chNFe>35240211222333000181550010000012341000001234</chNFe>\n'
        '  <CNPJ>11222333000181</CNPJ>\n'
        '  <xNome>DISTRIBUIDORA SAO PAULO LTDA</xNome>\n'
        '  <vNF>1850.50</vNF>\n'
        '  <dhEmi>2026-10-22T10:00:00-03:00</dhEmi>\n'
        '</resNFe>'
    )
    compressed = gzip.compress(xml_original.encode("utf-8"))
    b64_zip = base64.b64encode(compressed).decode("utf-8")

    decompressed = SefazDistribuicaoDFeService.decompress_gzip_b64(b64_zip)
    assert decompressed == xml_original

    doc_extraido = SefazDistribuicaoDFeService.parse_documento_extraido(
        nsu="000000000000016",
        schema="resNFe_v1.01.xsd",
        xml_conteudo=decompressed,
    )
    assert doc_extraido.chave_acesso == "35240211222333000181550010000012341000001234"
    assert doc_extraido.cnpj_emitente == "11222333000181"
    assert doc_extraido.nome_emitente == "DISTRIBUIDORA SAO PAULO LTDA"
    assert doc_extraido.valor_total == 1850.50
    assert doc_extraido.tipo_documento == "RESUMO"


def test_build_evento_manifestacao():
    """Valida a construção do XML do evento de manifestação."""
    # Ciência da Emissão
    xml_ciencia = SefazManifestacaoDestinatarioService.build_evento_xml(
        chave_acesso="35240211222333000181550010000012341000001234",
        cnpj_destinatario="98765432000100",
        tipo_evento=TP_CIENCIA,
    )
    assert "<tpEvento>210210</tpEvento>" in xml_ciencia
    assert "<descEvento>Ciencia da Emissao</descEvento>" in xml_ciencia

    # Operação Não Realizada com justificativa
    xml_nao_realizada = SefazManifestacaoDestinatarioService.build_evento_xml(
        chave_acesso="35240211222333000181550010000012341000001234",
        cnpj_destinatario="98765432000100",
        tipo_evento=TP_NAO_REALIZADA,
        justificativa="Mercadoria avariada durante transporte pelo fornecedor",
    )
    assert "<tpEvento>210240</tpEvento>" in xml_nao_realizada
    assert "<xJust>Mercadoria avariada durante transporte pelo fornecedor</xJust>" in xml_nao_realizada

    # Falha se justificativa menor que 15 chars para Não Realizada
    with pytest.raises(ValueError):
        SefazManifestacaoDestinatarioService.build_evento_xml(
            chave_acesso="35240211222333000181550010000012341000001234",
            cnpj_destinatario="98765432000100",
            tipo_evento=TP_NAO_REALIZADA,
            justificativa="Curto",
        )


def test_endpoint_sincronizar_inbound():
    """Testa a rota POST /api/v1/fiscal/inbound/sincronizar/{empresa_id}."""
    from app.api.v1.endpoints.inbound import get_db_session

    mock_session = MagicMock()
    mock_empresa = MagicMock()
    mock_empresa.id = "emp-uuid-123"
    mock_empresa.cnpj = "12345678000195"

    # Simula busca de empresa e notas
    mock_session.query.return_value.filter.return_value.first.side_effect = [
        mock_empresa,  # Busca empresa
        None,          # Busca ultima nota (ultNSU)
        None,          # Verifica nota existente
    ]

    def _mock_db_generator():
        yield mock_session

    app.dependency_overrides[get_db_session] = _mock_db_generator

    response = client.post("/api/v1/fiscal/inbound/sincronizar/emp-uuid-123")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["sucesso"] is True
    assert data["cnpj"] == "12345678000195"
    assert data["novos_documentos"] >= 1


def test_endpoint_manifestar():
    """Testa a rota POST /api/v1/fiscal/inbound/{chave}/manifestar."""
    from app.api.v1.endpoints.inbound import get_db_session

    mock_session = MagicMock()
    mock_nota = MagicMock()
    mock_nota.chave_acesso = "35240212345678000195550010000001231000001234"
    mock_nota.empresa_id = "emp-123"

    mock_empresa = MagicMock()
    mock_empresa.cnpj = "99888777000155"

    mock_session.query.return_value.filter.return_value.first.side_effect = [
        mock_nota,
        mock_empresa,
    ]

    def _mock_db_generator():
        yield mock_session

    app.dependency_overrides[get_db_session] = _mock_db_generator

    response = client.post(
        "/api/v1/fiscal/inbound/35240212345678000195550010000001231000001234/manifestar",
        json={"tipo_evento": "210210"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["sucesso"] is True
    assert data["novo_status_manifestacao"] == "CIENCIA"
    assert data["c_stat"] == 135
