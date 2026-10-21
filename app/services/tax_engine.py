"""Motor de Regras Tributárias e Cálculo para o Simples Nacional (CRT = 1).

Aplica a ABNT NBR 5891 (Arredondamento Half-Up / ROUND_HALF_UP) e valida as regras
específicas de CSOSN 101, 102/103 e 500, além do enquadramento de PIS/COFINS (CST 49/99).
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.canonical import DocumentoFiscalInput, ItemInput


TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def round_currency(val: Decimal) -> Decimal:
    """Arredonda para 2 casas decimais conforme ABNT NBR 5891 (ROUND_HALF_UP)."""
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def round_tax_rate(val: Decimal) -> Decimal:
    """Arredonda alíquotas com até 4 casas decimais."""
    return val.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


class ItemTributado(BaseModel):
    """Representação canônica do item após cálculo tributário para o Simples Nacional."""
    numero_item: int
    codigo: str
    descricao: str
    ncm: str
    cfop: str
    unidade: str
    quantidade: Decimal
    valor_unitario: Decimal
    desconto: Decimal
    frete: Decimal
    seguro: Decimal
    outras_despesas: Decimal
    valor_bruto: Decimal
    valor_total_liquido: Decimal

    # ICMS Simples Nacional
    origem: str
    csosn: str
    p_cred_sn: Optional[Decimal] = None
    v_cred_icms: Optional[Decimal] = None

    # Campos específicos CSOSN 500
    v_bc_st_ret: Optional[Decimal] = None
    p_st: Optional[Decimal] = None
    v_icms_substituto: Optional[Decimal] = None
    v_icms_st_ret: Optional[Decimal] = None

    # PIS e COFINS no Simples Nacional
    pis_cst: str = "49"
    pis_v_bc: Decimal = Decimal("0.00")
    pis_p_pis: Decimal = Decimal("0.00")
    pis_v_pis: Decimal = Decimal("0.00")

    cofins_cst: str = "49"
    cofins_v_bc: Decimal = Decimal("0.00")
    cofins_p_cofins: Decimal = Decimal("0.00")
    cofins_v_cofins: Decimal = Decimal("0.00")

    # Transparência fiscal
    v_tot_trib: Decimal = Decimal("0.00")


class TotaisDocumentoFiscal(BaseModel):
    """Totalizadores calculados do documento fiscal."""
    v_prod: Decimal = Field(..., description="Total dos produtos bruto")
    v_desc: Decimal = Field(..., description="Total de descontos")
    v_frete: Decimal = Field(..., description="Total de frete")
    v_seg: Decimal = Field(..., description="Total de seguro")
    v_outro: Decimal = Field(..., description="Total de outras despesas acessórias")
    v_nf: Decimal = Field(..., description="Valor total líquido da nota fiscal")
    v_tot_trib: Decimal = Field(..., description="Valor total aproximado de tributos")
    v_cred_icms_total: Decimal = Field(..., description="Total do crédito de ICMS aproveitável")
    v_troco: Decimal = Field(default=Decimal("0.00"), description="Valor do troco")


class DocumentoProcessado(BaseModel):
    """Documento fiscal consolidado após processamento das regras fiscais."""
    documento_original: DocumentoFiscalInput
    itens_tributados: List[ItemTributado]
    totais: TotaisDocumentoFiscal
    informacoes_complementares_geradas: str


class TaxEngineSimplesNacional:
    """Motor de cálculo fiscal para emitentes no Simples Nacional."""

    @classmethod
    def process(cls, doc: DocumentoFiscalInput) -> DocumentoProcessado:
        """Executa a validação, cálculo dos itens e apuração dos totais do documento."""
        if doc.emitente.crt != "1":
            raise ValueError("TaxEngineSimplesNacional aceita apenas emitentes com CRT = '1' (Simples Nacional).")

        itens_calculados: List[ItemTributado] = []
        tot_prod = Decimal("0.00")
        tot_desc = Decimal("0.00")
        tot_frete = Decimal("0.00")
        tot_seg = Decimal("0.00")
        tot_outro = Decimal("0.00")
        tot_trib = Decimal("0.00")
        tot_cred_icms = Decimal("0.00")

        for item in doc.itens:
            tributado = cls.calculate_item(item)
            itens_calculados.append(tributado)

            tot_prod += tributado.valor_bruto
            tot_desc += tributado.desconto
            tot_frete += tributado.frete
            tot_seg += tributado.seguro
            tot_outro += tributado.outras_despesas
            tot_trib += tributado.v_tot_trib
            if tributado.v_cred_icms:
                tot_cred_icms += tributado.v_cred_icms

        # Arredondamentos finais
        tot_prod = round_currency(tot_prod)
        tot_desc = round_currency(tot_desc)
        tot_frete = round_currency(tot_frete)
        tot_seg = round_currency(tot_seg)
        tot_outro = round_currency(tot_outro)
        tot_trib = round_currency(tot_trib)
        tot_cred_icms = round_currency(tot_cred_icms)

        # Regra SEFAZ: vNF = (vProd - vDesc - vICMSDeson) + vST + vFrete + vSeg + vOutro + vII + vIPI + vIPIDevol
        tot_nf = round_currency((tot_prod - tot_desc) + tot_frete + tot_seg + tot_outro)

        # Verificação do total de pagamentos x total da nota
        total_pago = sum((p.valor for p in doc.pagamentos), Decimal("0.00"))
        total_pago = round_currency(total_pago)

        v_troco = Decimal("0.00")
        if total_pago > tot_nf:
            v_troco = round_currency(total_pago - tot_nf)
        elif total_pago < tot_nf:
            raise ValueError(
                f"Soma dos pagamentos (R$ {total_pago}) é menor que o valor total da nota (R$ {tot_nf})."
            )

        totais = TotaisDocumentoFiscal(
            v_prod=tot_prod,
            v_desc=tot_desc,
            v_frete=tot_frete,
            v_seg=tot_seg,
            v_outro=tot_outro,
            v_nf=tot_nf,
            v_tot_trib=tot_trib,
            v_cred_icms_total=tot_cred_icms,
            v_troco=v_troco,
        )

        # Geração de mensagens fiscais obrigatórias do Simples Nacional (Art. 63 da Resolução CGSN nº 140/2018)
        inf_cpl_parts = []
        if doc.informacoes_complementares:
            inf_cpl_parts.append(doc.informacoes_complementares.strip())

        if tot_cred_icms > Decimal("0.00"):
            # Exige menção expressa de crédito
            inf_cpl_parts.append(
                f"PERMITE O APROVEITAMENTO DO CREDITO DE ICMS NO VALOR DE R$ {tot_cred_icms:.2f}."
            )
        else:
            inf_cpl_parts.append(
                "DOCUMENTO EMITIDO POR ME OU EPP OPTANTE PELO SIMPLES NACIONAL. NAO GERA DIREITO A CREDITO FISCAL DE IPI."
            )

        inf_cpl_final = " ; ".join(inf_cpl_parts)

        return DocumentoProcessado(
            documento_original=doc,
            itens_tributados=itens_calculados,
            totais=totais,
            informacoes_complementares_geradas=inf_cpl_final,
        )

    @classmethod
    def calculate_item(cls, item: ItemInput) -> ItemTributado:
        """Calcula tributos e valida regras específicas de cada item do Simples Nacional."""
        v_bruto = round_currency(item.quantidade * item.valor_unitario)
        desconto = round_currency(item.desconto)
        frete = round_currency(item.frete)
        seguro = round_currency(item.seguro)
        outras = round_currency(item.outras_despesas)
        v_liquido = round_currency((v_bruto - desconto) + frete + seguro + outras)

        v_trib = round_currency(item.valor_tributos_aproximado or Decimal("0.00"))

        p_cred_sn: Optional[Decimal] = None
        v_cred_icms: Optional[Decimal] = None
        v_bc_st_ret: Optional[Decimal] = None
        p_st: Optional[Decimal] = None
        v_icms_substituto: Optional[Decimal] = None
        v_icms_st_ret: Optional[Decimal] = None

        # Regras por CSOSN
        if item.csosn in ("101", "201"):
            # 101/201: Tributada pelo Simples Nacional com permissão de crédito
            if item.aliquota_credito_sn is None or item.aliquota_credito_sn <= Decimal("0"):
                raise ValueError(
                    f"Item {item.numero_item} com CSOSN {item.csosn} requer 'aliquota_credito_sn' maior que zero."
                )
            p_cred_sn = round_tax_rate(item.aliquota_credito_sn)
            # Base do crédito é o valor dos produtos deduzido de descontos
            base_credito = round_currency(v_bruto - desconto)
            v_cred_icms = round_currency(base_credito * (p_cred_sn / Decimal("100")))

        elif item.csosn in ("102", "103", "300", "400"):
            # 102/103/300/400: Sem permissão de crédito e sem cobrança de ICMS
            p_cred_sn = None
            v_cred_icms = None

        elif item.csosn == "500":
            # 500: ICMS cobrado anteriormente por substituição tributária (substituído) ou por antecipação
            p_cred_sn = None
            v_cred_icms = None

            # Valores de ST retidos anteriormente (opcionais ou preenchidos conforme necessidade do estado)
            v_bc_st_ret = round_currency(item.v_bc_st_ret or Decimal("0.00"))
            p_st = round_tax_rate(item.p_st or Decimal("0.00"))
            v_icms_substituto = round_currency(item.v_icms_substituto or Decimal("0.00"))
            v_icms_st_ret = round_currency(item.v_icms_st_ret or Decimal("0.00"))

        else:
            # Demais CSOSN (ex: 900)
            p_cred_sn = None
            v_cred_icms = None

        return ItemTributado(
            numero_item=item.numero_item,
            codigo=item.codigo,
            descricao=item.descricao,
            ncm=item.ncm,
            cfop=item.cfop,
            unidade=item.unidade,
            quantidade=item.quantidade,
            valor_unitario=item.valor_unitario,
            desconto=desconto,
            frete=frete,
            seguro=seguro,
            outras_despesas=outras,
            valor_bruto=v_bruto,
            valor_total_liquido=v_liquido,
            origem=item.origem,
            csosn=item.csosn,
            p_cred_sn=p_cred_sn,
            v_cred_icms=v_cred_icms,
            v_bc_st_ret=v_bc_st_ret,
            p_st=p_st,
            v_icms_substituto=v_icms_substituto,
            v_icms_st_ret=v_icms_st_ret,
            pis_cst="49",  # Outras Operações de Saída (sem valor a recolher no Simples)
            pis_v_bc=Decimal("0.00"),
            pis_p_pis=Decimal("0.00"),
            pis_v_pis=Decimal("0.00"),
            cofins_cst="49",
            cofins_v_bc=Decimal("0.00"),
            cofins_p_cofins=Decimal("0.00"),
            cofins_v_cofins=Decimal("0.00"),
            v_tot_trib=v_trib,
        )
