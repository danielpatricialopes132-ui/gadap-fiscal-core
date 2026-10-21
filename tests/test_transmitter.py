"""Testes unitários para o Cliente mTLS, Envelopamento SOAP 1.2 e Transmissor SEFAZ."""

from decimal import Decimal
import pytest
from lxml import etree

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
from app.services.sefaz.xml_builder import NFeXmlBuilder, NFE_NAMESPACE
from app.services.sefaz.xml_signer import XmlSigner
from app.services.sefaz.mtls_client import (
    SefazMtlsClient,
    SefazNetworkError,
    SefazSoapFaultError,
    SOAP12_NS,
    NFE_STATUS_WS_NS,
)
from app.services.sefaz.transmitter import (
    SefazTransmitter,
    SefazRejectionError,
    SefazStatusServicoResult,
    SefazAutorizacaoResult,
)
from tests.test_certificate import generate_self_signed_pfx
from app.core.security.certificate import A1CertificateManager


@pytest.fixture
def cert_manager() -> A1CertificateManager:
    password = "senha_teste_123"
    pfx_data = generate_self_signed_pfx(password=password)
    return A1CertificateManager(pfx_data=pfx_data, password=password)


@pytest.fixture
def signed_nfe_xml(cert_manager) -> etree._Element:
    emitente = EmitenteInput(
        cnpj="12345678000195",
        razao_social="EMITENTE TESTE",
        ie="123456789110",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua Teste",
            numero="1",
            bairro="Centro",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01001000",
        ),
    )

    destinatario = DestinatarioInput(
        cpf_cnpj="01234567890",
        razao_social="CLIENTE TESTE",
        ind_iedest="9",
        endereco=EnderecoInput(
            logradouro="Rua B",
            numero="2",
            bairro="Centro",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01001000",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="123",
        descricao="Item 1",
        ncm="84713012",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("100.00"),
        csosn="102",
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFE,
        numero=999,
        serie=1,
        emitente=emitente,
        destinatario=destinatario,
        itens=[item],
        pagamentos=[PagamentoInput(forma=FormaPagamento.DINHEIRO, valor=Decimal("100.00"))],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc)
    builder = NFeXmlBuilder(doc_proc, c_nf="12345678")
    raw_xml = builder.build()

    signer = XmlSigner(cert_manager)
    return signer.sign(raw_xml)


def test_soap12_envelope_wrapping():
    """Valida a construção do envelope SOAP 1.2 com o payload em nfeDadosMsg."""
    payload = "<teste>123</teste>"
    envelope = SefazMtlsClient.wrap_soap12_envelope(payload, NFE_STATUS_WS_NS)

    assert "<soap12:Envelope" in envelope
    assert f'xmlns:soap12="{SOAP12_NS}"' in envelope
    assert f'<nfeDadosMsg xmlns="{NFE_STATUS_WS_NS}">' in envelope
    assert "<teste>123</teste>" in envelope


def test_soap12_extract_body():
    """Valida extração do nó útil a partir de resposta SOAP 1.2."""
    xml_resp = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap12:Envelope xmlns:soap12="{SOAP12_NS}">
        <soap12:Body>
            <nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4">
                <retConsStatServ xmlns="http://www.portalfiscal.inf.br/nfe">
                    <cStat>107</cStat>
                    <xMotivo>Servico em Operacao</xMotivo>
                </retConsStatServ>
            </nfeResultMsg>
        </soap12:Body>
    </soap12:Envelope>
    """
    body = SefazMtlsClient.extract_soap12_body(xml_resp)
    assert body.tag.endswith("nfeResultMsg")
    ret = body.find(f".//{{{NFE_NAMESPACE}}}retConsStatServ") or body.find(".//retConsStatServ")
    assert ret is not None
    assert ret.findtext(f"{{{NFE_NAMESPACE}}}cStat") == "107"


def test_soap12_extract_fault_raises_error():
    """Valida detecção de SOAP Fault."""
    fault_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap12:Envelope xmlns:soap12="{SOAP12_NS}">
        <soap12:Body>
            <soap12:Fault>
                <soap12:Code><soap12:Value>soap12:Receiver</soap12:Value></soap12:Code>
                <soap12:Reason><soap12:Text>Erro interno na SEFAZ</soap12:Text></soap12:Reason>
            </soap12:Fault>
        </soap12:Body>
    </soap12:Envelope>
    """
    with pytest.raises(SefazSoapFaultError, match="SOAP Fault: .*Erro interno na SEFAZ"):
        SefazMtlsClient.extract_soap12_body(fault_xml)


def test_transmitter_consultar_status_servico_cstat_107(cert_manager, monkeypatch):
    """Valida o fluxo de consulta de status com retorno cStat=107 (Serviço em Operação)."""
    ret_xml = f"""
    <retConsStatServ xmlns="{NFE_NAMESPACE}" versao="4.00">
        <tpAmb>2</tpAmb>
        <verAplic>SP_NFE_PL_009_V4</verAplic>
        <cStat>107</cStat>
        <xMotivo>Servico em Operacao</xMotivo>
        <cUF>35</cUF>
        <dhRecbto>2026-10-21T12:00:00-03:00</dhRecbto>
        <tMed>1</tMed>
    </retConsStatServ>
    """
    mock_body = etree.fromstring(ret_xml.encode("utf-8"))

    client = SefazMtlsClient(cert_manager)
    monkeypatch.setattr(client, "post_soap", lambda url, envelope_xml, soap_action: mock_body)

    transmitter = SefazTransmitter(client)
    res = transmitter.consultar_status_servico(uf="SP")

    assert isinstance(res, SefazStatusServicoResult)
    assert res.c_stat == 107
    assert res.is_operacional is True
    assert res.x_motivo == "Servico em Operacao"
    assert res.t_med == 1


def test_transmitter_enviar_lote_sincrono_sucesso_nfe_proc(cert_manager, signed_nfe_xml, monkeypatch):
    """Valida retorno autorizado (cStat=100) e geração do documento legal <nfeProc>."""
    inf_nfe = signed_nfe_xml.find(f".//{{{NFE_NAMESPACE}}}infNFe")
    chave = inf_nfe.get("Id").replace("NFe", "")

    mock_resp_xml = f"""
    <retEnviNFe xmlns="{NFE_NAMESPACE}" versao="4.00">
        <tpAmb>2</tpAmb>
        <cStat>104</cStat>
        <xMotivo>Lote processado</xMotivo>
        <protNFe versao="4.00">
            <infProt>
                <tpAmb>2</tpAmb>
                <chNFe>{chave}</chNFe>
                <dhRecbto>2026-10-21T12:00:00-03:00</dhRecbto>
                <nProt>135260000000001</nProt>
                <digVal>abcdef123456=</digVal>
                <cStat>100</cStat>
                <xMotivo>Autorizado o uso da NF-e</xMotivo>
            </infProt>
        </protNFe>
    </retEnviNFe>
    """
    mock_body = etree.fromstring(mock_resp_xml.encode("utf-8"))

    client = SefazMtlsClient(cert_manager)
    monkeypatch.setattr(client, "post_soap", lambda url, envelope_xml, soap_action: mock_body)

    transmitter = SefazTransmitter(client)
    resultado = transmitter.enviar_lote_sincrono(xml_assinado=signed_nfe_xml, uf="SP")

    assert isinstance(resultado, SefazAutorizacaoResult)
    assert resultado.is_autorizado is True
    assert resultado.c_stat == 100
    assert resultado.n_prot == "135260000000001"
    assert resultado.chave_acesso == chave

    # Valida estrutura do XML definitivo nfeProc
    assert resultado.xml_proc is not None
    assert "<nfeProc" in resultado.xml_proc
    assert "<NFe" in resultado.xml_proc
    assert "<protNFe" in resultado.xml_proc


def test_transmitter_enviar_lote_rejeicao_sefaz_rejection_error(cert_manager, signed_nfe_xml, monkeypatch):
    """Valida lançamento de SefazRejectionError com sugestão legível para o usuário em rejeições (cStat >= 200)."""
    inf_nfe = signed_nfe_xml.find(f".//{{{NFE_NAMESPACE}}}infNFe")
    chave = inf_nfe.get("Id").replace("NFe", "")

    # Simula rejeição 204: Duplicidade de NF-e
    mock_resp_xml = f"""
    <retEnviNFe xmlns="{NFE_NAMESPACE}" versao="4.00">
        <tpAmb>2</tpAmb>
        <cStat>104</cStat>
        <xMotivo>Lote processado</xMotivo>
        <protNFe versao="4.00">
            <infProt>
                <tpAmb>2</tpAmb>
                <chNFe>{chave}</chNFe>
                <dhRecbto>2026-10-21T12:00:00-03:00</dhRecbto>
                <cStat>204</cStat>
                <xMotivo>Rejeicao: Duplicidade de NF-e</xMotivo>
            </infProt>
        </protNFe>
    </retEnviNFe>
    """
    mock_body = etree.fromstring(mock_resp_xml.encode("utf-8"))

    client = SefazMtlsClient(cert_manager)
    monkeypatch.setattr(client, "post_soap", lambda url, envelope_xml, soap_action: mock_body)

    transmitter = SefazTransmitter(client)

    with pytest.raises(SefazRejectionError) as exc_info:
        transmitter.enviar_lote_sincrono(xml_assinado=signed_nfe_xml, uf="SP")

    err = exc_info.value
    assert err.c_stat == 204
    assert "Duplicidade de NF-e" in err.x_motivo
    assert "Duplicidade de NF-e: Este número e série" in err.sugestao
    assert chave in str(err)


def test_transmitter_resiliencia_timeout_com_consulta_chave(cert_manager, signed_nfe_xml, monkeypatch):
    """Valida mecanismo de resiliência: se o POST da autorização der timeout, consulta a chave antes de falhar."""
    client = SefazMtlsClient(cert_manager)

    # 1. Simula Timeout de rede no envio
    def mock_post_timeout(url, envelope_xml, soap_action):
        raise SefazNetworkError("Read timed out")

    monkeypatch.setattr(client, "post_soap", mock_post_timeout)

    transmitter = SefazTransmitter(client)

    # 2. Simula que a consulta_chave_acesso descobre que a SEFAZ na verdade autorizou a nota
    inf_nfe = signed_nfe_xml.find(f".//{{{NFE_NAMESPACE}}}infNFe")
    chave = inf_nfe.get("Id").replace("NFe", "")

    monkeypatch.setattr(
        transmitter,
        "consultar_chave_acesso",
        lambda chave_acesso, uf, is_production: SefazAutorizacaoResult(
            c_stat=100,
            x_motivo="Autorizado o uso da NF-e",
            chave_acesso=chave,
            n_prot="999888777",
            is_autorizado=True,
        ),
    )

    # O método deve recuperar o resultado sem levantar exceção e sem reemitir
    res = transmitter.enviar_lote_sincrono(xml_assinado=signed_nfe_xml, uf="SP")
    assert res.is_autorizado is True
    assert res.n_prot == "999888777"
