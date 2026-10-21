"""Testes unitários para cenários fiscais Multi-UF (SP, BA, RJ, MG) e regras complexas SEFAZ."""

from decimal import Decimal
import pytest

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
from app.services.sefaz.access_key import build_access_key
from app.services.sefaz.xml_builder import NFeXmlBuilder, NFE_NAMESPACE
from app.services.sefaz.xsd_validator import XsdValidator
from app.core.uf_matrix import get_cuf_by_uf, get_uf_info


def test_uf_matrix_all_27_ufs_mapped():
    """Valida se todas as 27 UFs estão devidamente cadastradas com códigos IBGE e autorizadores."""
    ufs_esperadas = [
        "RO", "AC", "AM", "RR", "PA", "AP", "TO", "MA", "PI", "CE",
        "RN", "PB", "PE", "AL", "SE", "BA", "MG", "ES", "RJ", "SP",
        "PR", "SC", "RS", "MS", "MT", "GO", "DF"
    ]
    for uf in ufs_esperadas:
        info = get_uf_info(uf)
        assert info.sigla == uf
        assert len(info.codigo_ibge) == 2
        assert info.codigo_ibge.isdigit()
        assert info.autorizador_nfe in ("PROPRIO", "SVRS", "SVAN")
        assert info.autorizador_nfce in ("PROPRIO", "SVRS")


def test_cenario_a_operacao_interna_sp_sp():
    """Cenário A: Emissão interna SP -> SP com CSOSN 102 e CFOP 5102 deve gerar idDest=1."""
    emitente = EmitenteInput(
        cnpj="12345678000195",
        razao_social="EMITENTE PAULISTA LTDA",
        ie="123456789110",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua Direita",
            numero="100",
            bairro="Centro",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01001000",
        ),
    )

    destinatario = DestinatarioInput(
        cpf_cnpj="01234567890",
        razao_social="COMPRADOR PAULISTA",
        ind_iedest="9",
        endereco=EnderecoInput(
            logradouro="Rua Augusta",
            numero="200",
            bairro="Consolacao",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01304000",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="ITEM01",
        descricao="Produto Interno SP",
        ncm="84713012",
        cfop="5102",  # CFOP iniciando em 5 para interna
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("120.00"),
        csosn="102",
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFE,
        numero=101,
        serie=1,
        emitente=emitente,
        destinatario=destinatario,
        itens=[item],
        pagamentos=[PagamentoInput(forma=FormaPagamento.PIX, valor=Decimal("120.00"))],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc)
    builder = NFeXmlBuilder(doc_proc, c_nf="12345678")
    xml_element = builder.build()

    # Validações estruturais do Cenário A
    id_dest = xml_element.find(f".//{{{NFE_NAMESPACE}}}ide/{{{NFE_NAMESPACE}}}idDest")
    assert id_dest is not None and id_dest.text == "1"

    c_uf = xml_element.find(f".//{{{NFE_NAMESPACE}}}ide/{{{NFE_NAMESPACE}}}cUF")
    assert c_uf is not None and c_uf.text == "35"

    # Validação do Schema XSD
    XsdValidator.assert_valid(xml_element)


def test_cenario_a_rejeicao_cfop_incompativel_com_destino():
    """Valida bloqueio quando operação interestadual usar CFOP iniciado em 5."""
    emitente_sp = EmitenteInput(
        cnpj="12345678000195",
        razao_social="EMITENTE SP",
        ie="123456789110",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua A",
            numero="1",
            bairro="Centro",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01001000",
        ),
    )

    destinatario_ba = DestinatarioInput(
        cpf_cnpj="01234567890",
        razao_social="COMPRADOR BA",
        ind_iedest="9",
        endereco=EnderecoInput(
            logradouro="Av Oceânica",
            numero="50",
            bairro="Barra",
            codigo_municipio="2927408",
            nome_municipio="Salvador",
            uf="BA",
            cep="40140130",
        ),
    )

    # Item com CFOP 5102 (inválido para interestadual SP -> BA)
    item_invalido = ItemInput(
        numero_item=1,
        codigo="PROD01",
        descricao="Item CFOP Invalido",
        ncm="84713012",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("50.00"),
        csosn="102",
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFE,
        numero=102,
        serie=1,
        emitente=emitente_sp,
        destinatario=destinatario_ba,
        itens=[item_invalido],
        pagamentos=[PagamentoInput(forma=FormaPagamento.PIX, valor=Decimal("50.00"))],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc)
    with pytest.raises(ValueError, match="CFOP '5102' inconsistente com operação interestadual"):
        NFeXmlBuilder(doc_proc)


def test_cenario_b_interestadual_sp_para_ba_consumidor_final_simples_nacional():
    """Cenário B: SP -> BA consumidor final não-contribuinte (idDest 2, CFOP 6108, sem ICMSUFDest)."""
    emitente_sp = EmitenteInput(
        cnpj="12345678000195",
        razao_social="EMITENTE SP",
        ie="123456789110",
        crt="1",  # Simples Nacional
        endereco=EnderecoInput(
            logradouro="Rua da Consolacao",
            numero="100",
            bairro="Consolacao",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01301000",
        ),
    )

    destinatario_ba = DestinatarioInput(
        cpf_cnpj="01234567890",
        razao_social="CONSUMIDOR FINAL BAHIA",
        ind_iedest="9",  # Não contribuinte
        endereco=EnderecoInput(
            logradouro="Av Sete de Setembro",
            numero="300",
            bairro="Vitoria",
            codigo_municipio="2927408",
            nome_municipio="Salvador",
            uf="BA",
            cep="40080002",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="PROD6108",
        descricao="Venda de Mercadoria para Consumidor Final Outro Estado",
        ncm="84713012",
        cfop="6108",  # CFOP iniciando em 6
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("350.00"),
        csosn="102",
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFE,
        numero=103,
        serie=1,
        emitente=emitente_sp,
        destinatario=destinatario_ba,
        itens=[item],
        pagamentos=[PagamentoInput(forma=FormaPagamento.PIX, valor=Decimal("350.00"))],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc)
    builder = NFeXmlBuilder(doc_proc, c_nf="98765432")
    xml_element = builder.build()

    # Operação Interestadual: idDest = 2
    id_dest = xml_element.find(f".//{{{NFE_NAMESPACE}}}ide/{{{NFE_NAMESPACE}}}idDest")
    assert id_dest is not None and id_dest.text == "2"

    # Consumidor Final: indFinal = 1
    ind_final = xml_element.find(f".//{{{NFE_NAMESPACE}}}ide/{{{NFE_NAMESPACE}}}indFinal")
    assert ind_final is not None and ind_final.text == "1"

    # Não Contribuinte: indIEDest = 9
    ind_ie_dest = xml_element.find(f".//{{{NFE_NAMESPACE}}}dest/{{{NFE_NAMESPACE}}}indIEDest")
    assert ind_ie_dest is not None and ind_ie_dest.text == "9"

    # Regra STF ADI 5464: Emitente Simples Nacional NÃO DEVE gerar a tag ICMSUFDest
    icms_uf_dest = xml_element.find(f".//{{{NFE_NAMESPACE}}}ICMSUFDest")
    assert icms_uf_dest is None, "Simples Nacional não deve conter grupo ICMSUFDest"

    # Validação do Schema XSD
    XsdValidator.assert_valid(xml_element)


def test_cenario_c_emitente_bahia_chave_cuf_29_e_nfce_qr_code():
    """Cenário C: Emitente da Bahia (BA) deve gerar cUF=29 e chave iniciando com '29'."""
    assert get_cuf_by_uf("BA") == "29"

    emitente_ba = EmitenteInput(
        cnpj="98765432000188",
        razao_social="SUPERMERCADO BAHIANO LTDA",
        ie="987654321",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua Chile",
            numero="25",
            bairro="Centro Historico",
            codigo_municipio="2927408",
            nome_municipio="Salvador",
            uf="BA",
            cep="40020000",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="AGUA500",
        descricao="Agua Mineral 500ml",
        ncm="22011000",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("2.0000"),
        valor_unitario=Decimal("3.00"),
        csosn="102",
    )

    doc_nfce = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=888,
        serie=1,
        emitente=emitente_ba,
        destinatario=None,
        itens=[item],
        pagamentos=[PagamentoInput(forma=FormaPagamento.DINHEIRO, valor=Decimal("6.00"))],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc_nfce)
    builder = NFeXmlBuilder(doc_proc, c_nf="11223344")
    xml_element = builder.build()

    # Validação da Chave de Acesso da Bahia
    chave = builder.chave_acesso
    assert chave.startswith("29"), f"Chave de acesso da Bahia deve iniciar com '29', obtido: {chave}"
    assert len(chave) == 44

    # Validação do cUF no XML
    c_uf = xml_element.find(f".//{{{NFE_NAMESPACE}}}ide/{{{NFE_NAMESPACE}}}cUF")
    assert c_uf is not None and c_uf.text == "29"

    # Validação da URL do QR Code da Bahia (Cenário C)
    qr_code = xml_element.find(f".//{{{NFE_NAMESPACE}}}infNFeSupl/{{{NFE_NAMESPACE}}}qrCode")
    assert qr_code is not None
    assert "sefaz.ba.gov.br" in qr_code.text

    # Validação contra schema XSD
    XsdValidator.assert_valid(xml_element)


def test_cenario_d_substituicao_tributaria_csosn_500():
    """Cenário D: CSOSN 500 gera estrutura ICMSSN500 enxuta e válida no XSD."""
    emitente_sp = EmitenteInput(
        cnpj="12345678000195",
        razao_social="AUTO PECAS PAULISTA LTDA",
        ie="123456789110",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Av Santo Amaro",
            numero="400",
            bairro="Itaim",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="04505000",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="PEC001",
        descricao="Filtro de Oleo com ST Retido",
        ncm="84212300",
        cfop="5405",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("45.00"),
        csosn="500",
        # Sem retenções prévias a declarar
        v_bc_st_ret=Decimal("0.00"),
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=555,
        serie=1,
        emitente=emitente_sp,
        destinatario=None,
        itens=[item],
        pagamentos=[PagamentoInput(forma=FormaPagamento.CARTAO_DEBITO, valor=Decimal("45.00"))],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc)
    builder = NFeXmlBuilder(doc_proc, c_nf="55443322")
    xml_element = builder.build()

    icms_sn500 = xml_element.find(f".//{{{NFE_NAMESPACE}}}ICMSSN500")
    assert icms_sn500 is not None
    assert icms_sn500.find(f"{{{NFE_NAMESPACE}}}orig").text == "0"
    assert icms_sn500.find(f"{{{NFE_NAMESPACE}}}CSOSN").text == "500"

    # Bases retidas omitidas graciosamente quando 0.00
    assert icms_sn500.find(f"{{{NFE_NAMESPACE}}}vBCSTRet") is None

    # Validação do Schema XSD
    XsdValidator.assert_valid(xml_element)
