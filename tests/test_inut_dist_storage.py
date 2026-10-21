"""Testes para Inutilização de Numeração, Distribuição DF-e e Camada de Storage."""

import pytest
import os
import base64
from fastapi.testclient import TestClient

from app.main import app
from app.services.sefaz.inutilizacao import SefazInutilizacaoService
from app.services.sefaz.distribuicao import SefazDistribuicaoDFeService
from app.services.storage import FiscalStorageService
from app.schemas.canonical import DocumentoFiscalInput

client = TestClient(app)


def test_inutilizacao_build_and_service():
    xml_raw, inut_id = SefazInutilizacaoService.build_inut_xml(
        uf="SP",
        ano=2026,
        cnpj="11222333000181",
        modelo="55",
        serie=1,
        n_nf_ini=10,
        n_nf_fin=15,
        justificativa="NUMERACAO PULADA POR FALHA DE SISTEMA LOCAL",
        tp_amb=2,
    )
    assert inut_id.startswith("ID3526")
    assert "<inutNFe" in xml_raw
    assert "<nNFIni>10</nNFIni>" in xml_raw

    service = SefazInutilizacaoService()
    res = service.inutilizar_faixa(
        uf="SP",
        ano=2026,
        cnpj="11222333000181",
        modelo="55",
        serie=1,
        n_nf_ini=10,
        n_nf_fin=15,
        justificativa="NUMERACAO PULADA POR FALHA DE SISTEMA LOCAL",
    )
    assert res.c_stat == 102
    assert res.is_homologado is True
    assert res.n_prot is not None
    assert "<procInutNFe" in res.xml_proc_inut


def test_api_inutilizar_endpoint():
    payload = {
        "uf": "SP",
        "ano": 2026,
        "cnpj": "11222333000181",
        "modelo": "55",
        "serie": 1,
        "numero_inicial": 20,
        "numero_final": 25,
        "justificativa": "PULOU NUMERACAO DE TESTES DO SIMPLES",
    }
    resp = client.post("/api/v1/fiscal/inutilizar", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sucesso"] is True
    assert data["c_stat"] == 102
    assert data["xml_proc_inut_b64"] is not None


def test_distribuicao_dfe_service_and_endpoint():
    service = SefazDistribuicaoDFeService()
    res = service.consultar_dfe(cnpj="11222333000181", ult_nsu="0")
    assert res.c_stat == 138
    assert len(res.documentos) > 0
    assert res.documentos[0].resumo is True

    # Rota GET
    resp = client.get("/api/v1/fiscal/distribuicao/consultar?cnpj=11222333000181&ult_nsu=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["c_stat"] == 138
    assert data["quantidade_documentos"] >= 1

    # Rota POST Manifestação
    manif_payload = {
        "chave_acesso": "35261011222333000181550010000000011123456789",
        "cnpj_destinatario": "11222333000181",
        "tipo_evento": "210210",
    }
    resp_manif = client.post("/api/v1/fiscal/distribuicao/manifestar", json=manif_payload)
    assert resp_manif.status_code == 200
    res_data = resp_manif.json()
    assert res_data["sucesso"] is True
    assert res_data["c_stat"] == 135


def test_fiscal_storage_service(tmp_path):
    storage = FiscalStorageService(base_dir=str(tmp_path))
    res = storage.registrar_documento(
        tipo_documento="NFE",
        chave_acesso="35261011222333000181550010000000011123456789",
        numero=1,
        serie=1,
        emitente_cnpj="11222333000181",
        destinatario_doc="99888777000161",
        valor_total=100.0,
        status="AUTORIZADA",
        xml_conteudo="<nfeProc>teste</nfeProc>",
        pdf_bytes=b"%PDF-1.4 mock",
    )
    assert os.path.exists(res["caminho_xml_local"])
    assert os.path.exists(res["caminho_pdf_local"])
