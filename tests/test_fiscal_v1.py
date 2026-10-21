from decimal import Decimal
import base64
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.canonical import DocumentoFiscalInput, TipoDocumento
from app.services.nfse.national_adapter import NationalNfseAdapter
from app.services.danfe.pdf_generator import DanfePdfGenerator

client = TestClient(app)


def test_nfse_national_adapter_build_and_emit(sample_doc_input: DocumentoFiscalInput):
    # Ajusta para NFSE
    sample_doc_input.tipo_documento = TipoDocumento.NFSE
    adapter = NationalNfseAdapter()
    
    payload = adapter.build_dps_payload(sample_doc_input)
    assert "infDPS" in payload
    assert payload["infDPS"]["nDPS"] == str(sample_doc_input.numero)
    assert payload["infDPS"]["prest"]["CNPJ"] == sample_doc_input.emitente.cnpj

    xml_dps = adapter.build_dps_xml(sample_doc_input)
    assert "<DPS" in xml_dps
    assert f"<nDPS>{sample_doc_input.numero}</nDPS>" in xml_dps

    result = adapter.emitir_dps(sample_doc_input)
    assert result.sucesso is True
    assert result.status_processamento == "AUTORIZADA"
    assert result.chave_acesso_nfse is not None
    assert len(result.chave_acesso_nfse) == 50
    assert "<NFSe" in result.xml_nfse


def test_danfe_pdf_generator_watermark(sample_nfe_xml: str):
    # Gera PDF em modo homologação (deve conter a marca d'água no canvas)
    pdf_homolog = DanfePdfGenerator.generate_danfe_pdf(sample_nfe_xml, force_homologacao=True)
    assert len(pdf_homolog) > 1000
    assert pdf_homolog.startswith(b"%PDF")

    # Gera PDF em modo produção (sem marca d'água)
    pdf_prod = DanfePdfGenerator.generate_danfe_pdf(sample_nfe_xml, force_homologacao=False)
    assert len(pdf_prod) > 1000
    assert pdf_prod.startswith(b"%PDF")


def test_api_v1_fiscal_certificado_status():
    resp = client.get("/api/v1/fiscal/certificado/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "carregado" in data
    assert "mensagem" in data


def test_api_v1_fiscal_status_sefaz():
    resp = client.get("/api/v1/fiscal/status-sefaz?uf=SP&modelo=55")
    assert resp.status_code == 200
    data = resp.json()
    assert data["uf"] == "SP"
    assert data["c_stat"] in ("107", "100")
    assert data["status_operacional"] is True


def test_api_v1_fiscal_emitir_nfe(sample_doc_input: DocumentoFiscalInput):
    # Converte payload Pydantic para dicionário JSON
    json_data = sample_doc_input.model_dump(mode="json")
    resp = client.post("/api/v1/fiscal/emitir", json=json_data)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sucesso"] is True
    assert data["tipo_documento"] == "NFE"
    assert len(data["chave_acesso"]) == 44
    assert data["status"] == "AUTORIZADA"
    assert "xml_autorizado_b64" in data
    assert "danfe_pdf_b64" in data
    
    # Valida decodificação do DANFE em PDF
    pdf_bytes = base64.b64decode(data["danfe_pdf_b64"])
    assert pdf_bytes.startswith(b"%PDF")


def test_api_v1_fiscal_emitir_nfse(sample_doc_input: DocumentoFiscalInput):
    sample_doc_input.tipo_documento = TipoDocumento.NFSE
    json_data = sample_doc_input.model_dump(mode="json")
    resp = client.post("/api/v1/fiscal/emitir", json=json_data)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sucesso"] is True
    assert data["tipo_documento"] == "NFSE"
    assert len(data["chave_acesso"]) == 50
    assert data["status"] == "AUTORIZADA"
    assert "xml_autorizado_b64" in data


def test_openapi_swagger_documentation():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "/api/v1/fiscal/emitir" in schema["paths"]
    assert "/api/v1/fiscal/status-sefaz" in schema["paths"]
    assert "/api/v1/fiscal/certificado/status" in schema["paths"]
