"""Testes de integração para os endpoints REST da FastAPI, geração de DANFE e cancelamento/CC-e."""

from decimal import Decimal
import base64
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.canonical import (
    DocumentoFiscalInput,
    EmitenteInput,
    DestinatarioInput,
    EnderecoInput,
    ItemInput,
    PagamentoInput,
    TipoDocumento,
    FormaPagamento,
)
from app.services.tax_engine import TaxEngineSimplesNacional
from app.services.sefaz.xml_builder import NFeXmlBuilder
from app.services.sefaz.xml_signer import XmlSigner
from app.services.sefaz.danfe_generator import DanfePdfGenerator
from app.core.config import settings
from app.core.security.certificate import A1CertificateManager
from tests.test_certificate import generate_self_signed_pfx


client = TestClient(app)


@pytest.fixture
def cert_setup(monkeypatch):
    password = "fastapi_test_password"
    pfx_data = generate_self_signed_pfx(password=password)
    b64_pfx = base64.b64encode(pfx_data).decode("ascii")

    monkeypatch.setattr(settings, "CERTIFICATE_BASE64", b64_pfx)
    monkeypatch.setattr(settings, "CERTIFICATE_PASSWORD", password)
    monkeypatch.setattr(settings, "CERTIFICATE_PATH", None)

    return A1CertificateManager(pfx_data=pfx_data, password=password)


@pytest.fixture
def valid_nfe_payload() -> dict:
    return {
        "tipo_documento": "NFE",
        "natureza_operacao": "VENDA DE MERCADORIA",
        "serie": 1,
        "numero": 1234,
        "emitente": {
            "cnpj": "12345678000195",
            "razao_social": "EMPRESA MODELO ME",
            "ie": "123456789110",
            "crt": "1",
            "endereco": {
                "logradouro": "Rua Boa Vista",
                "numero": "50",
                "bairro": "Centro",
                "codigo_municipio": "3550308",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "cep": "01014000",
            },
        },
        "destinatario": {
            "cpf_cnpj": "01234567890",
            "razao_social": "CLIENTE CONSUMIDOR",
            "ind_iedest": "9",
            "endereco": {
                "logradouro": "Rua Direita",
                "numero": "20",
                "bairro": "Centro",
                "codigo_municipio": "3550308",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "cep": "01002000",
            },
        },
        "itens": [
            {
                "numero_item": 1,
                "codigo": "ITEM01",
                "descricao": "Mouse USB Optico",
                "ncm": "84716053",
                "cfop": "5102",
                "unidade": "UN",
                "quantidade": 2.0,
                "valor_unitario": 45.0,
                "desconto": 0.0,
                "csosn": "102",
            }
        ],
        "pagamentos": [
            {
                "forma": "17",
                "valor": 90.0,
            }
        ],
    }


def test_api_root_and_health():
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "online"

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"


def test_api_status_servico_mock(cert_setup, monkeypatch):
    from app.services.sefaz.transmitter import SefazTransmitter, SefazStatusServicoResult

    monkeypatch.setattr(
        SefazTransmitter,
        "consultar_status_servico",
        lambda self, uf, modelo: SefazStatusServicoResult(
            c_stat=107,
            x_motivo="Servico em Operacao",
            tp_amb=2,
            dh_retorno="2026-10-21T12:00:00-03:00",
            t_med=1,
            is_operacional=True,
        ),
    )

    response = client.post("/api/v1/dfe/status-servico", json={"uf": "SP", "modelo": "55"})
    assert response.status_code == 200
    data = response.json()
    assert data["operacional"] is True
    assert data["c_stat"] == 107


def test_api_emitir_documento_fiscal_sucesso(cert_setup, valid_nfe_payload, monkeypatch):
    from app.services.sefaz.transmitter import SefazTransmitter, SefazAutorizacaoResult

    # Mock do envio SEFAZ com retorno autorizado cStat 100
    monkeypatch.setattr(
        SefazTransmitter,
        "enviar_lote_sincrono",
        lambda self, xml_assinado, uf, modelo: SefazAutorizacaoResult(
            c_stat=100,
            x_motivo="Autorizado o uso da NF-e",
            chave_acesso="35261012345678000195550010000012341123456780",
            n_prot="135260000099999",
            dh_recbto="2026-10-21T12:00:00-03:00",
            xml_proc="<nfeProc versao='4.00'><NFe/><protNFe/></nfeProc>",
            is_autorizado=True,
        ),
    )

    response = client.post("/api/v1/dfe/emitir", json=valid_nfe_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AUTORIZADO"
    assert data["numero_protocolo"] == "135260000099999"
    assert data["c_stat"] == 100
    assert len(data["xml_autorizado_b64"]) > 0


def test_danfe_pdf_generation_nfe(cert_setup, valid_nfe_payload):
    """Valida a geração de DANFE PDF (A4) a partir de XML assinado."""
    doc_in = DocumentoFiscalInput(**valid_nfe_payload)
    doc_proc = TaxEngineSimplesNacional.process(doc_in)
    builder = NFeXmlBuilder(doc_proc, c_nf="12345678")
    raw_xml = builder.build()

    signer = XmlSigner(cert_setup)
    signed_xml_bytes = signer.sign_to_xml_bytes(raw_xml)

    pdf_bytes = DanfePdfGenerator.generate_danfe_pdf(signed_xml_bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

    # Testa endpoint da API
    b64_xml = base64.b64encode(signed_xml_bytes).decode("ascii")
    res = client.post("/api/v1/dfe/danfe/pdf", json={"xml_b64": b64_xml})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")


def test_danfe_pdf_generation_nfce(cert_setup):
    """Valida a geração de DANFE NFC-e (Bobina 80mm com QR Code)."""
    emitente = EmitenteInput(
        cnpj="12345678000195",
        razao_social="MERCADO EXPRESS ME",
        ie="123456789110",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua do Comercio",
            numero="5",
            bairro="Centro",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01001000",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="PROD01",
        descricao="Refrigerante 2L",
        ncm="22021000",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("1.0"),
        valor_unitario=Decimal("8.50"),
        csosn="102",
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=555,
        serie=1,
        emitente=emitente,
        destinatario=None,
        itens=[item],
        pagamentos=[PagamentoInput(forma=FormaPagamento.DINHEIRO, valor=Decimal("8.50"))],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc)
    builder = NFeXmlBuilder(doc_proc, c_nf="88776655")
    raw_xml = builder.build()

    signer = XmlSigner(cert_setup)
    signed_xml_bytes = signer.sign_to_xml_bytes(raw_xml)

    pdf_bytes = DanfePdfGenerator.generate_danfe_pdf(signed_xml_bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")
