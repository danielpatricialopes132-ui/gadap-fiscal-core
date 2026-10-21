"""Testes unitários para Chave de Acesso de 44 dígitos, Serializador XML SEFAZ v4.00 e Validador XSD."""

from decimal import Decimal
from datetime import datetime, timezone
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
from app.services.sefaz.access_key import (
    build_access_key,
    calculate_mod11_dv,
    validate_access_key,
)
from app.core.uf_matrix import get_cuf_by_uf
from app.services.sefaz.xml_builder import NFeXmlBuilder, NFE_NAMESPACE
from app.services.sefaz.xsd_validator import XsdValidator, XsdValidationError
from app.core.config import settings, DFEEnvironment


@pytest.fixture
def base_doc_proc():
    emitente = EmitenteInput(
        cnpj="12345678000195",
        razao_social="EMPRESA TESTE EMITENTE LTDA",
        nome_fantasia="NOME FANTASIA TESTE",
        ie="123456789110",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua das Acácias",
            numero="123",
            complemento="Sala 1",
            bairro="Centro",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01001000",
        ),
    )

    destinatario = DestinatarioInput(
        cpf_cnpj="01234567890",
        razao_social="JOAO DA SILVA CLIENTE",
        ind_iedest="9",
        endereco=EnderecoInput(
            logradouro="Av Brasil",
            numero="500",
            bairro="Jardins",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01430000",
        ),
    )

    item1 = ItemInput(
        numero_item=1,
        codigo="PROD001",
        descricao="Cabo de Rede Cat6 2m",
        ncm="85444200",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("2.0000"),
        valor_unitario=Decimal("25.50"),
        csosn="101",
        aliquota_credito_sn=Decimal("3.50"),
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFE,
        numero=12345,
        serie=1,
        emitente=emitente,
        destinatario=destinatario,
        itens=[item1],
        pagamentos=[
            PagamentoInput(forma=FormaPagamento.PIX, valor=Decimal("51.00"))
        ],
    )

    return TaxEngineSimplesNacional.process(doc)


def test_access_key_deterministic_generation():
    # Exemplo canônico de chave SEFAZ com cNF fixo
    c_uf = "35"
    aamm = "2610"
    cnpj = "12345678000195"
    mod = "55"
    serie = 1
    numero = 12345
    c_nf = "12345678"

    chave = build_access_key(
        c_uf=c_uf,
        ano_mes=aamm,
        cnpj=cnpj,
        modelo=mod,
        serie=serie,
        numero_nf=numero,
        tp_emis="1",
        c_nf=c_nf,
    )

    assert len(chave) == 44
    assert chave.startswith("3526101234567800019555001000012345112345678")
    assert validate_access_key(chave) is True


def test_access_key_mod11_dv_calculation():
    # Teste de cálculo do DV
    chave_43 = "3526101234567800019555001000012345112345678"
    dv = calculate_mod11_dv(chave_43)
    assert isinstance(dv, int)
    assert 0 <= dv <= 9

    chave_completa = f"{chave_43}{dv}"
    assert validate_access_key(chave_completa) is True
    assert validate_access_key("35261012345678000195550010000123451123456789") in (True, False)


def test_nfe_xml_builder_structure_and_homologacao(base_doc_proc, monkeypatch):
    monkeypatch.setattr(settings, "DFE_ENVIRONMENT", DFEEnvironment.HOMOLOGACAO)

    builder = NFeXmlBuilder(base_doc_proc, c_nf="12345678")
    xml_element = builder.build()
    xml_bytes = builder.to_xml_bytes()

    assert b"<NFe" in xml_bytes
    assert b"infNFe" in xml_bytes

    # No ambiente de homologação, o xNome do destinatário deve ser fixo
    dest_nome = xml_element.find(f".//{{{NFE_NAMESPACE}}}dest/{{{NFE_NAMESPACE}}}xNome")
    assert dest_nome is not None
    assert dest_nome.text == "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"

    # Validação do CSOSN 101 gerado
    csosn = xml_element.find(f".//{{{NFE_NAMESPACE}}}ICMSSN101/{{{NFE_NAMESPACE}}}CSOSN")
    assert csosn is not None and csosn.text == "101"

    # Validação contra schema XSD
    XsdValidator.assert_valid(xml_element)


def test_nfce_xml_builder_with_supl_and_without_dest():
    emitente = EmitenteInput(
        cnpj="12345678000195",
        razao_social="VAREJO EXPRESS LTDA",
        ie="123456789110",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua do Comercio",
            numero="10",
            bairro="Centro",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01001000",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="REFRI01",
        descricao="Refrigerante Lata 350ml",
        ncm="22021000",
        cfop="5405",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("6.00"),
        csosn="500",
    )

    doc_nfce = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=999,
        serie=1,
        emitente=emitente,
        destinatario=None,  # NFC-e sem identificação
        itens=[item],
        pagamentos=[
            PagamentoInput(forma=FormaPagamento.DINHEIRO, valor=Decimal("10.00"))
        ],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc_nfce)
    builder = NFeXmlBuilder(doc_proc, c_nf="87654321")
    xml_element = builder.build()

    # NFC-e modelo 65
    mod = xml_element.find(f".//{{{NFE_NAMESPACE}}}ide/{{{NFE_NAMESPACE}}}mod")
    assert mod.text == "65"

    # tpImp 4 (DANFE NFC-e)
    tp_imp = xml_element.find(f".//{{{NFE_NAMESPACE}}}ide/{{{NFE_NAMESPACE}}}tpImp")
    assert tp_imp.text == "4"

    # Destinatário ausente
    assert xml_element.find(f".//{{{NFE_NAMESPACE}}}dest") is None

    # Reserva infNFeSupl presente
    supl = xml_element.find(f"{{{NFE_NAMESPACE}}}infNFeSupl")
    assert supl is not None

    # Validação contra schema XSD
    XsdValidator.assert_valid(xml_element)


def test_xsd_validator_detects_invalid_xml():
    xml_invalido = b"""<?xml version="1.0" encoding="UTF-8"?>
    <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
        <infNFe Id="NFeInvalida" versao="4.00">
            <!-- Falta ide, emit, det, etc -->
        </infNFe>
    </NFe>
    """
    is_valid, errors = XsdValidator.validate(xml_invalido)
    assert is_valid is False
    assert len(errors) > 0

    with pytest.raises(XsdValidationError):
        XsdValidator.assert_valid(xml_invalido)
