"""Testes unitários para o TaxEngineSimplesNacional cobrindo CSOSN 101, 102 e 500,

com validação de precisão de centavos e arredondamento ABNT NBR 5891.
"""

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
from app.services.tax_engine import TaxEngineSimplesNacional, round_currency


@pytest.fixture
def base_emitente() -> EmitenteInput:
    return EmitenteInput(
        cnpj="12345678000195",
        razao_social="EMPRESA MODELO SIMPLES NACIONAL LTDA",
        nome_fantasia="LOJA EXEMPLO",
        ie="123456789110",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua das Flores",
            numero="100",
            bairro="Centro",
            codigo_municipio="3550308",  # São Paulo - SP
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01001000",
        ),
    )


@pytest.fixture
def base_destinatario() -> DestinatarioInput:
    return DestinatarioInput(
        cpf_cnpj="01234567890",
        razao_social="CONSUMIDOR FINAL TESTE",
        ind_iedest="9",
        endereco=EnderecoInput(
            logradouro="Av Paulista",
            numero="1500",
            bairro="Bela Vista",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01310100",
        ),
    )


def test_tax_engine_csosn_101_calculo_credito(base_emitente, base_destinatario):
    """CSOSN 101 deve calcular pCredSN e vCredICMS sobre valor líquido do produto."""
    item = ItemInput(
        numero_item=1,
        codigo="PROD001",
        descricao="Produto com Permissao de Credito",
        ncm="84713012",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("3.0000"),
        valor_unitario=Decimal("150.33"),  # Bruto = 450.99
        desconto=Decimal("10.00"),          # Líquido = 440.99
        csosn="101",
        aliquota_credito_sn=Decimal("2.82"),  # 440.99 * 0.0282 = 12.435918 -> 12.44 (Half-Up)
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFE,
        numero=1001,
        serie=1,
        emitente=base_emitente,
        destinatario=base_destinatario,
        itens=[item],
        pagamentos=[
            PagamentoInput(forma=FormaPagamento.PIX, valor=Decimal("440.99"))
        ],
    )

    proc = TaxEngineSimplesNacional.process(doc)
    item_trib = proc.itens_tributados[0]

    assert item_trib.csosn == "101"
    assert item_trib.p_cred_sn == Decimal("2.8200")
    assert item_trib.v_cred_icms == Decimal("12.44")
    assert proc.totais.v_prod == Decimal("450.99")
    assert proc.totais.v_desc == Decimal("10.00")
    assert proc.totais.v_nf == Decimal("440.99")
    assert proc.totais.v_cred_icms_total == Decimal("12.44")
    assert "PERMITE O APROVEITAMENTO DO CREDITO" in proc.informacoes_complementares_geradas
    assert "12.44" in proc.informacoes_complementares_geradas


def test_tax_engine_csosn_101_sem_aliquota_gera_erro(base_emitente, base_destinatario):
    """CSOSN 101 sem aliquota_credito_sn informada deve levantar erro."""
    item = ItemInput(
        numero_item=1,
        codigo="PROD001",
        descricao="Produto 101 Invalido",
        ncm="84713012",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("100.00"),
        csosn="101",
        aliquota_credito_sn=None,
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFE,
        numero=1002,
        serie=1,
        emitente=base_emitente,
        destinatario=base_destinatario,
        itens=[item],
        pagamentos=[
            PagamentoInput(forma=FormaPagamento.DINHEIRO, valor=Decimal("100.00"))
        ],
    )

    with pytest.raises(ValueError, match="requer 'aliquota_credito_sn' maior que zero"):
        TaxEngineSimplesNacional.process(doc)


def test_tax_engine_csosn_102_sem_credito(base_emitente, base_destinatario):
    """CSOSN 102/103 não deve destacar nem permitir crédito de ICMS."""
    item = ItemInput(
        numero_item=1,
        codigo="PROD102",
        descricao="Produto Simples Sem Credito",
        ncm="61091000",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("2.0000"),
        valor_unitario=Decimal("49.99"),  # Bruto = 99.98
        desconto=Decimal("0.00"),
        csosn="102",
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=501,
        serie=1,
        emitente=base_emitente,
        destinatario=None,  # NFC-e permite consumidor anônimo
        itens=[item],
        pagamentos=[
            PagamentoInput(forma=FormaPagamento.CARTAO_DEBITO, valor=Decimal("99.98"))
        ],
    )

    proc = TaxEngineSimplesNacional.process(doc)
    item_trib = proc.itens_tributados[0]

    assert item_trib.csosn == "102"
    assert item_trib.p_cred_sn is None
    assert item_trib.v_cred_icms is None
    assert proc.totais.v_cred_icms_total == Decimal("0.00")
    assert item_trib.pis_cst == "49"
    assert item_trib.cofins_cst == "49"
    assert item_trib.pis_v_pis == Decimal("0.00")
    assert item_trib.cofins_v_cofins == Decimal("0.00")
    assert "NAO GERA DIREITO A CREDITO FISCAL DE IPI" in proc.informacoes_complementares_geradas


def test_tax_engine_csosn_500_substituicao_tributaria(base_emitente, base_destinatario):
    """CSOSN 500 para mercadorias com ICMS ST retido anteriormente."""
    item = ItemInput(
        numero_item=1,
        codigo="BEB001",
        descricao="Refrigerante Lata 350ml ST",
        ncm="22021000",
        cfop="5405",
        unidade="UN",
        quantidade=Decimal("10.0000"),
        valor_unitario=Decimal("5.50"),   # Bruto = 55.00
        csosn="500",
        v_bc_st_ret=Decimal("50.00"),
        p_st=Decimal("18.00"),
        v_icms_substituto=Decimal("9.00"),
        v_icms_st_ret=Decimal("9.00"),
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=502,
        serie=1,
        emitente=base_emitente,
        destinatario=None,
        itens=[item],
        pagamentos=[
            PagamentoInput(forma=FormaPagamento.PIX, valor=Decimal("55.00"))
        ],
    )

    proc = TaxEngineSimplesNacional.process(doc)
    item_trib = proc.itens_tributados[0]

    assert item_trib.csosn == "500"
    assert item_trib.p_cred_sn is None
    assert item_trib.v_cred_icms is None
    assert item_trib.v_bc_st_ret == Decimal("50.00")
    assert item_trib.p_st == Decimal("18.0000")
    assert item_trib.v_icms_st_ret == Decimal("9.00")
    assert proc.totais.v_nf == Decimal("55.00")


def test_tax_engine_arredondamento_nbr5891():
    """Valida regra de arredondamento Half-Up (ABNT NBR 5891)."""
    assert round_currency(Decimal("10.125")) == Decimal("10.13")
    assert round_currency(Decimal("10.124")) == Decimal("10.12")
    assert round_currency(Decimal("10.126")) == Decimal("10.13")


def test_tax_engine_pagamento_com_troco(base_emitente, base_destinatario):
    """Valida cálculo de troco quando valor pago excede o total da nota."""
    item = ItemInput(
        numero_item=1,
        codigo="PROD01",
        descricao="Item Simples",
        ncm="84713012",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("85.50"),
        csosn="102",
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=503,
        serie=1,
        emitente=base_emitente,
        destinatario=None,
        itens=[item],
        pagamentos=[
            PagamentoInput(forma=FormaPagamento.DINHEIRO, valor=Decimal("100.00"))
        ],
    )

    proc = TaxEngineSimplesNacional.process(doc)
    assert proc.totais.v_nf == Decimal("85.50")
    assert proc.totais.v_troco == Decimal("14.50")


def test_tax_engine_pagamento_insuficiente_lanca_erro(base_emitente, base_destinatario):
    """Pagamento menor que o total da nota deve gerar exceção."""
    item = ItemInput(
        numero_item=1,
        codigo="PROD01",
        descricao="Item Simples",
        ncm="84713012",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("100.00"),
        csosn="102",
    )

    doc = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=504,
        serie=1,
        emitente=base_emitente,
        destinatario=None,
        itens=[item],
        pagamentos=[
            PagamentoInput(forma=FormaPagamento.DINHEIRO, valor=Decimal("90.00"))
        ],
    )

    with pytest.raises(ValueError, match="Soma dos pagamentos.*é menor que o valor total da nota"):
        TaxEngineSimplesNacional.process(doc)
