"""Schemas canônicos de entrada para emissão de Documentos Fiscais Eletrônicos (DF-e).

Isolam o ERP/API das particularidades estruturais do XML da SEFAZ.
Todos os campos quantitativos, percentuais e monetários utilizam estritamente Decimal.
Inclui chave de idempotência (idempotency_key) para resiliência na submissão.
"""

from decimal import Decimal
from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class TipoDocumento(str, Enum):
    NFE = "NFE"      # Modelo 55
    NFCE = "NFCE"    # Modelo 65
    NFSE = "NFSE"    # Nota Fiscal de Serviços Eletrônica


class FormaPagamento(str, Enum):
    DINHEIRO = "01"
    CHEQUE = "02"
    CARTAO_CREDITO = "03"
    CARTAO_DEBITO = "04"
    CREDITO_LOJA = "05"
    VALE_ALIMENTACAO = "10"
    VALE_REFEICAO = "11"
    VALE_PRESENTE = "12"
    VALE_COMBUSTIVEL = "13"
    BOLETO_BANCARIO = "15"
    DEPOSITO_BANCARIO = "16"
    PIX = "17"
    TRANSFERENCIA_BANCARIA = "18"
    PROGRAMA_FIDELIDADE = "19"
    SEM_PAGAMENTO = "90"
    OUTROS = "99"


class EnderecoInput(BaseModel):
    logradouro: str = Field(..., min_length=1, max_length=60, description="Logradouro / Rua / Avenida")
    numero: str = Field(..., min_length=1, max_length=60, description="Número ou S/N")
    complemento: Optional[str] = Field(None, max_length=60, description="Complemento")
    bairro: str = Field(..., min_length=1, max_length=60, description="Bairro")
    codigo_municipio: str = Field(..., min_length=7, max_length=7, description="Código IBGE do município (7 dígitos)")
    nome_municipio: str = Field(..., min_length=1, max_length=60, description="Nome do município")
    uf: str = Field(..., min_length=2, max_length=2, description="Sigla da UF (ex: SP, RJ, MG)")
    cep: str = Field(..., min_length=8, max_length=8, description="CEP apenas dígitos (8 números)")

    @field_validator("cep", "codigo_municipio")
    @classmethod
    def only_digits(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        return digits

    @field_validator("uf")
    @classmethod
    def uppercase_uf(cls, v: str) -> str:
        return v.upper()


class EmitenteInput(BaseModel):
    cnpj: str = Field(..., description="CNPJ do emitente (14 dígitos numéricos)")
    razao_social: str = Field(..., min_length=2, max_length=60, description="Razão Social do Emitente")
    nome_fantasia: Optional[str] = Field(None, max_length=60, description="Nome Fantasia")
    ie: str = Field(..., min_length=2, max_length=14, description="Inscrição Estadual")
    crt: Literal["1"] = Field(
        default="1",
        description="Código de Regime Tributário: 1 = Simples Nacional",
    )
    endereco: EnderecoInput

    @field_validator("cnpj")
    @classmethod
    def clean_cnpj(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        if len(digits) != 14:
            raise ValueError("CNPJ do emitente deve conter exatamente 14 dígitos numéricos.")
        return digits


class DestinatarioInput(BaseModel):
    cpf_cnpj: str = Field(..., description="CPF (11 dígitos) ou CNPJ (14 dígitos)")
    razao_social: str = Field(..., min_length=2, max_length=60, description="Razão Social ou Nome do Destinatário")
    ie: Optional[str] = Field(None, description="Inscrição Estadual (obrigatória se ind_iedest = '1')")
    ind_iedest: Literal["1", "2", "9"] = Field(
        default="9",
        description="1 = Contribuinte ICMS, 2 = Contribuinte Isento, 9 = Não Contribuinte",
    )
    email: Optional[str] = Field(None, max_length=60, description="E-mail para envio do XML/DANFE")
    endereco: Optional[EnderecoInput] = Field(
        None,
        description="Endereço do destinatário (obrigatório para NF-e mod 55)",
    )

    @field_validator("cpf_cnpj")
    @classmethod
    def clean_cpf_cnpj(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        if len(digits) not in (11, 14):
            raise ValueError("Documento do destinatário deve ser CPF (11 dígitos) ou CNPJ (14 dígitos).")
        return digits

    @model_validator(mode="after")
    def validate_ie_dest(self) -> "DestinatarioInput":
        if self.ind_iedest == "1" and not self.ie:
            raise ValueError("Inscrição Estadual (IE) é obrigatória quando ind_iedest = '1' (Contribuinte ICMS).")
        return self


class ItemInput(BaseModel):
    numero_item: int = Field(..., ge=1, le=990, description="Número sequencial do item na nota (1 a 990)")
    codigo: str = Field(..., min_length=1, max_length=60, description="Código interno do produto")
    descricao: str = Field(..., min_length=1, max_length=120, description="Descrição clara do produto")
    ncm: str = Field(..., min_length=8, max_length=8, description="NCM com 8 dígitos numéricos")
    cfop: str = Field(..., min_length=4, max_length=4, description="CFOP com 4 dígitos")
    unidade: str = Field(..., min_length=1, max_length=6, description="Unidade comercial (ex: UN, KG, CX)")
    quantidade: Decimal = Field(..., gt=Decimal("0"), description="Quantidade comercial")
    valor_unitario: Decimal = Field(..., gt=Decimal("0"), description="Valor unitário de comercialização")
    desconto: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Valor do desconto no item")
    outras_despesas: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Outras despesas acessórias")
    frete: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Rateio de frete")
    seguro: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Rateio de seguro")

    # Tributação Simples Nacional
    origem: Literal["0", "1", "2", "3", "4", "5", "6", "7", "8"] = Field(
        default="0",
        description="Origem da mercadoria (0=Nacional, 1=Estrangeira direta, 2=Estrangeira interna, etc.)",
    )
    csosn: Literal["101", "102", "103", "201", "202", "203", "300", "400", "500", "900"] = Field(
        default="102",
        description="Código de Situação da Operação no Simples Nacional",
    )

    # Parâmetros fiscais complementares para CSOSN 101/201
    aliquota_credito_sn: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Alíquota aplicável de cálculo do crédito de ICMS (% pCredSN)",
    )

    # Campos específicos para CSOSN 500 (ICMS Cobrado anteriormente por Substituição Tributária)
    v_bc_st_ret: Optional[Decimal] = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Base de cálculo do ICMS ST retido")
    p_st: Optional[Decimal] = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Alíquota do ICMS ST retido")
    v_icms_substituto: Optional[Decimal] = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Valor do ICMS próprio do substituto")
    v_icms_st_ret: Optional[Decimal] = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Valor do ICMS ST retido anteriormente")

    # Transparência fiscal (Lei 12.741/2012 / IBPT)
    valor_tributos_aproximado: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Valor aproximado dos tributos federais, estaduais e municipais",
    )

    @field_validator("ncm", "cfop")
    @classmethod
    def clean_fiscal_codes(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        return digits

    @property
    def valor_bruto(self) -> Decimal:
        """Valor bruto do item antes de desconto e acréscimos."""
        return self.quantidade * self.valor_unitario

    @property
    def valor_total_liquido(self) -> Decimal:
        """Valor total líquido: (qCom * vUnCom) - Desconto + Frete + Seguro + Outras Despesas."""
        return (self.valor_bruto - self.desconto) + self.frete + self.seguro + self.outras_despesas


class PagamentoInput(BaseModel):
    forma: FormaPagamento = Field(..., description="Meio de pagamento SEFAZ")
    valor: Decimal = Field(..., gt=Decimal("0"), description="Valor do pagamento em Decimal")
    descricao_outros: Optional[str] = Field(None, max_length=60, description="Descrição se forma = 99")


class DocumentoFiscalInput(BaseModel):
    idempotency_key: Optional[str] = Field(
        None,
        max_length=64,
        description="Chave única de idempotência do ERP solicitante para evitar duplicidade de emissão",
    )
    tipo_documento: TipoDocumento = Field(..., description="Tipo do documento: NFE (55), NFCE (65) ou NFSE")
    natureza_operacao: str = Field(default="VENDA DE MERCADORIA", min_length=1, max_length=60)
    serie: int = Field(default=1, ge=1, le=999)
    numero: int = Field(..., ge=1, le=999999999)
    emitente: EmitenteInput
    destinatario: Optional[DestinatarioInput] = Field(
        None,
        description="Destinatário (opcional em NFC-e com valor até o limite legal, obrigatório em NF-e)",
    )
    itens: List[ItemInput] = Field(..., min_length=1, max_length=990)
    pagamentos: List[PagamentoInput] = Field(..., min_length=1)
    informacoes_complementares: Optional[str] = Field(
        None,
        max_length=5000,
        description="Informações complementares de interesse do contribuinte (infCpl)",
    )

    @model_validator(mode="after")
    def validate_rules_by_tipo(self) -> "DocumentoFiscalInput":
        if self.tipo_documento == TipoDocumento.NFE:
            if not self.destinatario:
                raise ValueError("NF-e (modelo 55) exige a identificação do destinatário.")
            if not self.destinatario.endereco:
                raise ValueError("NF-e (modelo 55) exige endereço completo do destinatário.")
        return self
