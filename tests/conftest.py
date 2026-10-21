import pytest
from decimal import Decimal
import base64
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


@pytest.fixture
def sample_doc_input() -> DocumentoFiscalInput:
    return DocumentoFiscalInput(
        idempotency_key="TEST-IDEMP-001",
        tipo_documento=TipoDocumento.NFE,
        natureza_operacao="VENDA DE MERCADORIA",
        serie=1,
        numero=1234,
        emitente=EmitenteInput(
            cnpj="11222333000181",
            razao_social="EMPRESA MODELO SIMPLES NACIONAL LTDA",
            ie="123456789",
            crt="1",
            endereco=EnderecoInput(
                logradouro="RUA DAS FLORES",
                numero="100",
                bairro="CENTRO",
                codigo_municipio="3550308",
                nome_municipio="SAO PAULO",
                uf="SP",
                cep="01001000",
            ),
        ),
        destinatario=DestinatarioInput(
            cpf_cnpj="99888777000161",
            razao_social="CLIENTE TESTE LTDA",
            ie="987654321",
            ind_iedest="1",
            endereco=EnderecoInput(
                logradouro="AV BRASIL",
                numero="500",
                bairro="JARDINS",
                codigo_municipio="3550308",
                nome_municipio="SAO PAULO",
                uf="SP",
                cep="01430000",
            ),
        ),
        itens=[
            ItemInput(
                numero_item=1,
                codigo="PROD001",
                descricao="PRODUTO TESTE 1",
                ncm="84713012",
                cfop="5102",
                unidade="UN",
                quantidade=Decimal("2.0000"),
                valor_unitario=Decimal("150.00"),
                desconto=Decimal("10.00"),
                csosn="102",
            )
        ],
        pagamentos=[
            PagamentoInput(
                forma=FormaPagamento.PIX,
                valor=Decimal("290.00"),
            )
        ],
    )


@pytest.fixture
def sample_nfe_xml(sample_doc_input: DocumentoFiscalInput) -> str:
    xml, _ = NFeXmlBuilder.build_from_input(sample_doc_input)
    return xml
