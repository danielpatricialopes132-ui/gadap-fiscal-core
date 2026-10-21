"""Testes automatizados para a Etapa 8: Idempotência, Supabase Storage e Fechamento Contábil."""

import pytest
import zipfile
from io import BytesIO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db_session
from app.services.emission_orchestrator import EmissionOrchestrator
from app.services.storage.supabase_storage import SupabaseStorageService
from app.schemas.canonical import DocumentoFiscalInput

# Banco de dados SQLite isolado em memória com StaticPool para compartilhar dados
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db_session] = override_get_db
client = TestClient(app)


@pytest.fixture
def test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_supabase_storage_service():
    storage = SupabaseStorageService()
    # Upload de teste
    xml_path = storage.salvar_xml_autorizado(
        chave_acesso="35261011222333000181550010000012341297617328",
        xml_conteudo="<nfeProc versao='4.00'><NFe></NFe></nfeProc>",
    )
    assert "35261011222333000181550010000012341297617328" in xml_path

    url_temp = storage.obter_url_download_temporaria(xml_path)
    assert url_temp is not None
    assert len(url_temp) > 10


def test_emission_orchestrator_idempotencia(test_db, sample_doc_input: DocumentoFiscalInput):
    sample_doc_input.idempotency_key = "IDEMP-TEST-ORCH-001"
    orchestrator = EmissionOrchestrator(db=test_db)

    # 1ª Submissão: Deve processar e autorizar
    res1 = orchestrator.processar_emissao(sample_doc_input)
    assert res1["sucesso"] is True
    assert res1["idempotente"] is False
    assert res1["status"] == "AUTORIZADA"
    assert res1["chave_acesso"] is not None

    # 2ª Submissão com a MESMA chave de idempotência: Deve retornar imediatamente sem reprocessar
    res2 = orchestrator.processar_emissao(sample_doc_input)
    assert res2["sucesso"] is True
    assert res2["idempotente"] is True
    assert res2["chave_acesso"] == res1["chave_acesso"]
    assert res2["status"] == "AUTORIZADA"


def test_api_listagem_documentos_e_fechamento(sample_doc_input: DocumentoFiscalInput):
    # Garante que há ao menos 1 documento emitido
    db = TestingSessionLocal()
    orchestrator = EmissionOrchestrator(db=db)
    sample_doc_input.idempotency_key = "IDEMP-API-TEST-002"
    orchestrator.processar_emissao(sample_doc_input)
    db.close()

    # GET /api/v1/fiscal/documentos
    resp_list = client.get("/api/v1/fiscal/documentos?pagina=1&limite=10")
    assert resp_list.status_code == 200
    data = resp_list.json()
    assert data["total"] >= 1
    assert len(data["itens"]) >= 1

    chave = data["itens"][0]["chave_acesso"]

    # GET /api/v1/fiscal/documentos/{chave}/download/xml
    resp_down = client.get(f"/api/v1/fiscal/documentos/{chave}/download/xml")
    assert resp_down.status_code == 200

    # GET /api/v1/fiscal/fechamento-mensal
    resp_zip = client.get("/api/v1/fiscal/fechamento-mensal?ano=2026&mes=10")
    assert resp_zip.status_code == 200
    assert resp_zip.headers["content-type"] == "application/zip"

    # Valida estrutura do arquivo ZIP retornado
    zip_buf = BytesIO(resp_zip.content)
    with zipfile.ZipFile(zip_buf, "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) >= 1
        assert any(chave in name for name in namelist)
