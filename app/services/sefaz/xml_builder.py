"""Serializador de Documentos Fiscais Eletrônicos (NF-e mod 55 e NFC-e mod 65) em XML SEFAZ v4.00.

Gera a árvore XML completa em conformidade com o Manual de Orientação do Contribuinte (MOC 7.0 / NT 2020.005),
com suporte dinâmico a cenários Multi-UF:
- Cenário A: Operação Interna (idDest=1, CFOP 5xxx) vs. Interestadual (idDest=2, CFOP 6xxx)
- Cenário B: Não Contribuinte / B2C Interestadual no Simples Nacional (isento de ICMSUFDest / ADI 5464)
- Cenário C: Emitente na Bahia (BA) com QR Code oficial da SEFAZ-BA
- Cenário D: Substituição Tributária (CSOSN 500) com omissão graciosa de bases não retidas
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from lxml import etree

from app.schemas.canonical import TipoDocumento
from app.services.tax_engine import DocumentoProcessado, TaxEngineSimplesNacional
from app.services.sefaz.access_key import build_access_key
from app.core.uf_matrix import get_cuf_by_uf, get_nfce_qr_code_url
from app.core.config import settings, DFEEnvironment


# Namespace padrão da NF-e v4.00
NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
NFE_NSMAP = {None: NFE_NAMESPACE}


class NFeXmlBuilder:
    """Construtor de XML da NF-e (55) e NFC-e (65) no padrão SEFAZ v4.00."""

    def __init__(self, doc_proc: DocumentoProcessado, data_emissao: Optional[datetime] = None, c_nf: str = ""):
        self.doc_proc = doc_proc
        self.doc = doc_proc.documento_original
        self.totais = doc_proc.totais
        self.itens = doc_proc.itens_tributados

        self.data_emissao = data_emissao or datetime.now(timezone.utc)
        self.is_nfce = self.doc.tipo_documento == TipoDocumento.NFCE
        self.modelo = "65" if self.is_nfce else "55"
        self.is_homologacao = settings.DFE_ENVIRONMENT == DFEEnvironment.HOMOLOGACAO

        # UFs do emitente e destinatário
        self.uf_emitente = self.doc.emitente.endereco.uf.strip().upper()
        self.c_uf = get_cuf_by_uf(self.uf_emitente)

        # Determinação de Operação Interna vs. Interestadual (Cenário A)
        self.uf_destinatario: Optional[str] = None
        if self.doc.destinatario and self.doc.destinatario.endereco:
            self.uf_destinatario = self.doc.destinatario.endereco.uf.strip().upper()

        if self.is_nfce or not self.uf_destinatario or (self.uf_destinatario == self.uf_emitente):
            self.id_dest = "1"  # Operação Interna
        else:
            self.id_dest = "2"  # Operação Interestadual

        self._validate_cfop_dest_destination()

        # Chave de acesso de 44 dígitos
        self.ano_mes = self.data_emissao.strftime("%y%m")
        self.chave_acesso = build_access_key(
            c_uf=self.c_uf,
            ano_mes=self.ano_mes,
            cnpj=self.doc.emitente.cnpj,
            modelo=self.modelo,
            serie=self.doc.serie,
            numero_nf=self.doc.numero,
            tp_emis="1",  # 1=Normal
            c_nf=c_nf,
        )

    @classmethod
    def build_from_input(cls, doc_input, data_emissao: Optional[datetime] = None) -> tuple[str, str]:
        """Constrói o XML da NF-e/NFC-e diretamente a partir de um DocumentoFiscalInput."""
        doc_proc = TaxEngineSimplesNacional.calculate_document(doc_input)
        builder = cls(doc_proc=doc_proc, data_emissao=data_emissao)
        xml_bytes = builder.to_xml_bytes()
        return xml_bytes.decode("utf-8"), builder.chave_acesso

    def _validate_cfop_dest_destination(self) -> None:
        """Valida se os CFOPs dos itens são coerentes com o destino da operação (Cenário A)."""
        expected_prefix = "5" if self.id_dest == "1" else "6"
        for item in self.itens:
            cfop = item.cfop.strip()
            if not cfop.startswith(expected_prefix):
                tipo_op = "interna" if self.id_dest == "1" else "interestadual"
                raise ValueError(
                    f"Item {item.numero_item}: CFOP '{cfop}' inconsistente com operação {tipo_op} "
                    f"(idDest={self.id_dest}). CFOP esperado iniciando com '{expected_prefix}'."
                )

    def _el(self, parent: etree._Element, tag: str, text: Optional[str] = None) -> etree._Element:
        """Cria e anexa um elemento XML filho com texto."""
        element = etree.SubElement(parent, f"{{{NFE_NAMESPACE}}}{tag}")
        if text is not None:
            element.text = str(text)
        return element

    def build(self) -> etree._Element:
        """Monta a árvore XML completa (elemento <NFe>)."""
        nfe = etree.Element(f"{{{NFE_NAMESPACE}}}NFe", nsmap=NFE_NSMAP)
        inf_nfe = etree.SubElement(
            nfe,
            f"{{{NFE_NAMESPACE}}}infNFe",
            Id=f"NFe{self.chave_acesso}",
            versao="4.00",
        )

        self._build_ide(inf_nfe)
        self._build_emit(inf_nfe)
        self._build_dest(inf_nfe)
        self._build_itens(inf_nfe)
        self._build_total(inf_nfe)
        self._build_transp(inf_nfe)
        self._build_cobr(inf_nfe)
        self._build_pag(inf_nfe)
        self._build_inf_adic(inf_nfe)

        # Se for NFC-e, anexa o nó infNFeSupl com a URL correta por estado (Cenário C)
        if self.is_nfce:
            self._build_inf_nfe_supl(nfe)

        return nfe

    def to_xml_bytes(self, pretty_print: bool = False) -> bytes:
        """Serializa a árvore XML em bytes UTF-8 com declaração XML."""
        root = self.build()
        return etree.tostring(
            root,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=pretty_print,
        )

    def _build_ide(self, parent: etree._Element) -> None:
        """Grupo <ide>: Identificação do documento fiscal."""
        ide = self._el(parent, "ide")
        self._el(ide, "cUF", self.c_uf)
        self._el(ide, "cNF", self.chave_acesso[35:43])
        self._el(ide, "natOp", self.doc.natureza_operacao[:60])
        self._el(ide, "mod", self.modelo)
        self._el(ide, "serie", str(self.doc.serie))
        self._el(ide, "nNF", str(self.doc.numero))

        dh_emi = self.data_emissao.strftime("%Y-%m-%dT%H:%M:%S%z")
        if not self.data_emissao.tzinfo:
            dh_emi = f"{self.data_emissao.strftime('%Y-%m-%dT%H:%M:%S')}-03:00"
        self._el(ide, "dhEmi", dh_emi)

        self._el(ide, "tpNF", "1")  # 1=Saída
        self._el(ide, "idDest", self.id_dest)  # 1=Interna, 2=Interestadual (Cenário A)
        self._el(ide, "cMunFG", self.doc.emitente.endereco.codigo_municipio)

        # Formato de Impressão do DANFE: 1=Retrato (NF-e), 4=DANFE NFC-e
        tp_imp = "4" if self.is_nfce else "1"
        self._el(ide, "tpImp", tp_imp)

        self._el(ide, "tpEmis", "1")  # 1=Normal
        self._el(ide, "cDV", self.chave_acesso[43])
        self._el(ide, "tpAmb", str(settings.tp_amb))
        self._el(ide, "finNFe", "1")  # 1=Normal
        self._el(ide, "indFinal", "1")  # 1=Consumidor final (Cenário B)
        self._el(ide, "indPres", "1")   # 1=Operação presencial
        self._el(ide, "procEmi", "0")  # 0=Aplicativo do contribuinte
        self._el(ide, "verProc", settings.APP_VERSION)

    def _build_emit(self, parent: etree._Element) -> None:
        """Grupo <emit>: Identificação do Emitente (Simples Nacional)."""
        emit = self._el(parent, "emit")
        self._el(emit, "CNPJ", self.doc.emitente.cnpj)
        self._el(emit, "xNome", self.doc.emitente.razao_social[:60])
        if self.doc.emitente.nome_fantasia:
            self._el(emit, "xFant", self.doc.emitente.nome_fantasia[:60])

        ender_emit = self._el(emit, "enderEmit")
        end = self.doc.emitente.endereco
        self._el(ender_emit, "xLgr", end.logradouro[:60])
        self._el(ender_emit, "nro", end.numero[:60])
        if end.complemento:
            self._el(ender_emit, "xCpl", end.complemento[:60])
        self._el(ender_emit, "xBairro", end.bairro[:60])
        self._el(ender_emit, "cMun", end.codigo_municipio)
        self._el(ender_emit, "xMun", end.nome_municipio[:60])
        self._el(ender_emit, "UF", end.uf)
        self._el(ender_emit, "CEP", end.cep)
        self._el(ender_emit, "cPais", "1058")
        self._el(ender_emit, "xPais", "Brasil")

        self._el(emit, "IE", self.doc.emitente.ie)
        self._el(emit, "CRT", self.doc.emitente.crt)

    def _build_dest(self, parent: etree._Element) -> None:
        """Grupo <dest>: Identificação do Destinatário com comutação de homologação."""
        dest_input = self.doc.destinatario

        if self.is_nfce and not dest_input:
            return

        if not dest_input:
            return

        dest = self._el(parent, "dest")
        doc_digits = dest_input.cpf_cnpj
        if len(doc_digits) == 14:
            self._el(dest, "CNPJ", doc_digits)
        else:
            self._el(dest, "CPF", doc_digits)

        if self.is_homologacao:
            self._el(dest, "xNome", "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL")
        else:
            self._el(dest, "xNome", dest_input.razao_social[:60])

        if dest_input.endereco:
            ender_dest = self._el(dest, "enderDest")
            end = dest_input.endereco
            self._el(ender_dest, "xLgr", end.logradouro[:60])
            self._el(ender_dest, "nro", end.numero[:60])
            if end.complemento:
                self._el(ender_dest, "xCpl", end.complemento[:60])
            self._el(ender_dest, "xBairro", end.bairro[:60])
            self._el(ender_dest, "cMun", end.codigo_municipio)
            self._el(ender_dest, "xMun", end.nome_municipio[:60])
            self._el(ender_dest, "UF", end.uf)
            self._el(ender_dest, "CEP", end.cep)
            self._el(ender_dest, "cPais", "1058")
            self._el(ender_dest, "xPais", "Brasil")

        self._el(dest, "indIEDest", dest_input.ind_iedest)
        if dest_input.ind_iedest == "1" and dest_input.ie:
            self._el(dest, "IE", dest_input.ie)

        if dest_input.email:
            self._el(dest, "email", dest_input.email[:60])

    def _build_itens(self, parent: etree._Element) -> None:
        """Grupo <det>: Detalhamento de produtos, serviços e tributação."""
        for item in self.itens:
            det = etree.SubElement(parent, f"{{{NFE_NAMESPACE}}}det", nItem=str(item.numero_item))

            prod = self._el(det, "prod")
            self._el(prod, "cProd", item.codigo[:60])
            self._el(prod, "cEAN", "SEM GTIN")
            self._el(prod, "xProd", item.descricao[:120])
            self._el(prod, "NCM", item.ncm)
            self._el(prod, "CFOP", item.cfop)
            self._el(prod, "uCom", item.unidade[:6])
            self._el(prod, "qCom", f"{item.quantidade:.4f}")
            self._el(prod, "vUnCom", f"{item.valor_unitario:.4f}")
            self._el(prod, "vProd", f"{item.valor_bruto:.2f}")
            self._el(prod, "cEANTrib", "SEM GTIN")
            self._el(prod, "uTrib", item.unidade[:6])
            self._el(prod, "qTrib", f"{item.quantidade:.4f}")
            self._el(prod, "vUnTrib", f"{item.valor_unitario:.4f}")

            if item.frete > Decimal("0.00"):
                self._el(prod, "vFrete", f"{item.frete:.2f}")
            if item.seguro > Decimal("0.00"):
                self._el(prod, "vSeg", f"{item.seguro:.2f}")
            if item.desconto > Decimal("0.00"):
                self._el(prod, "vDesc", f"{item.desconto:.2f}")
            if item.outras_despesas > Decimal("0.00"):
                self._el(prod, "vOutro", f"{item.outras_despesas:.2f}")

            self._el(prod, "indTot", "1")

            imposto = self._el(det, "imposto")
            if item.v_tot_trib > Decimal("0.00"):
                self._el(imposto, "vTotTrib", f"{item.v_tot_trib:.2f}")

            icms = self._el(imposto, "ICMS")
            self._build_icms_sn(icms, item)

            # Cenário B: CRT = 1 (Simples Nacional) NUNCA gera ICMSUFDest (DIFAL da EC 87/2015 suspenso pelo STF)
            # O grupo ICMSUFDest é omitido propositalmente para emitentes optantes pelo Simples Nacional.

            # PIS
            pis = self._el(imposto, "PIS")
            pis_outr = self._el(pis, "PISOutr")
            self._el(pis_outr, "CST", item.pis_cst)
            self._el(pis_outr, "vBC", f"{item.pis_v_bc:.2f}")
            self._el(pis_outr, "pPIS", f"{item.pis_p_pis:.2f}")
            self._el(pis_outr, "vPIS", f"{item.pis_v_pis:.2f}")

            # COFINS
            cofins = self._el(imposto, "COFINS")
            cofins_outr = self._el(cofins, "COFINSOutr")
            self._el(cofins_outr, "CST", item.cofins_cst)
            self._el(cofins_outr, "vBC", f"{item.cofins_v_bc:.2f}")
            self._el(cofins_outr, "pCOFINS", f"{item.cofins_p_cofins:.2f}")
            self._el(cofins_outr, "vCOFINS", f"{item.cofins_v_cofins:.2f}")

    def _build_icms_sn(self, parent: etree._Element, item) -> None:
        """Gera o nó específico do ICMS no Simples Nacional conforme CSOSN (Cenário D)."""
        csosn = item.csosn
        tag_name = f"ICMSSN{csosn}"
        icms_node = self._el(parent, tag_name)
        self._el(icms_node, "orig", str(item.origem))
        self._el(icms_node, "CSOSN", csosn)

        if csosn in ("101", "201"):
            self._el(icms_node, "pCredSN", f"{item.p_cred_sn:.4f}")
            self._el(icms_node, "vCredICMSSN", f"{item.v_cred_icms:.2f}")

        elif csosn == "500":
            # Cenário D: Monta ICMSSN500 apenas com orig e CSOSN se não houver retenção anterior a declarar
            if item.v_bc_st_ret and item.v_bc_st_ret > Decimal("0.00"):
                self._el(icms_node, "vBCSTRet", f"{item.v_bc_st_ret:.2f}")
                self._el(icms_node, "pST", f"{item.p_st:.4f}")
                self._el(icms_node, "vICMSSubstituto", f"{item.v_icms_substituto:.2f}")
                self._el(icms_node, "vICMSSTRet", f"{item.v_icms_st_ret:.2f}")

    def _build_total(self, parent: etree._Element) -> None:
        """Grupo <total>: Valores totais consolidados da nota."""
        total = self._el(parent, "total")
        icms_tot = self._el(total, "ICMSTot")

        self._el(icms_tot, "vBC", "0.00")
        self._el(icms_tot, "vICMS", "0.00")
        self._el(icms_tot, "vICMSDeson", "0.00")
        self._el(icms_tot, "vFCP", "0.00")
        self._el(icms_tot, "vBCST", "0.00")
        self._el(icms_tot, "vST", "0.00")
        self._el(icms_tot, "vFCPST", "0.00")
        self._el(icms_tot, "vFCPSTRet", "0.00")
        self._el(icms_tot, "vProd", f"{self.totais.v_prod:.2f}")
        self._el(icms_tot, "vFrete", f"{self.totais.v_frete:.2f}")
        self._el(icms_tot, "vSeg", f"{self.totais.v_seg:.2f}")
        self._el(icms_tot, "vDesc", f"{self.totais.v_desc:.2f}")
        self._el(icms_tot, "vII", "0.00")
        self._el(icms_tot, "vIPI", "0.00")
        self._el(icms_tot, "vIPIDevol", "0.00")
        self._el(icms_tot, "vPIS", "0.00")
        self._el(icms_tot, "vCOFINS", "0.00")
        self._el(icms_tot, "vOutro", f"{self.totais.v_outro:.2f}")
        self._el(icms_tot, "vNF", f"{self.totais.v_nf:.2f}")
        if self.totais.v_tot_trib > Decimal("0.00"):
            self._el(icms_tot, "vTotTrib", f"{self.totais.v_tot_trib:.2f}")

    def _build_transp(self, parent: etree._Element) -> None:
        """Grupo <transp>: Modalidade do frete (9=Sem Ocorrência de Transporte)."""
        transp = self._el(parent, "transp")
        self._el(transp, "modFrete", "9")

    def _build_cobr(self, parent: etree._Element) -> None:
        """Grupo <cobr>: Dados de fatura."""
        pass

    def _build_pag(self, parent: etree._Element) -> None:
        """Grupo <pag>: Detalhamento das formas de pagamento e troco."""
        pag = self._el(parent, "pag")
        for p in self.doc.pagamentos:
            det_pag = self._el(pag, "detPag")
            self._el(det_pag, "tPag", p.forma.value)
            self._el(det_pag, "vPag", f"{p.valor:.2f}")
            if p.forma.value == "99" and p.descricao_outros:
                self._el(det_pag, "xPag", p.descricao_outros[:60])

        if self.totais.v_troco > Decimal("0.00"):
            self._el(pag, "vTroco", f"{self.totais.v_troco:.2f}")

    def _build_inf_adic(self, parent: etree._Element) -> None:
        """Grupo <infAdic>: Informações complementares de interesse do contribuinte."""
        inf_adic = self._el(parent, "infAdic")
        msg = self.doc_proc.informacoes_complementares_geradas[:5000]
        self._el(inf_adic, "infCpl", msg)

    def _build_inf_nfe_supl(self, parent: etree._Element) -> None:
        """Grupo <infNFeSupl>: QR Code e URL de consulta oficial da UF do emitente (Cenário C)."""
        qr_url = get_nfce_qr_code_url(self.uf_emitente, is_production=not self.is_homologacao)

        supl = self._el(parent, "infNFeSupl")
        self._el(supl, "qrCode", f"{qr_url}?p={self.chave_acesso}|2|{settings.tp_amb}|{settings.active_csc_id}")
        self._el(supl, "urlChave", qr_url)
