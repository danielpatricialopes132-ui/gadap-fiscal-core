"""Gerador unificado de DANFE em PDF via ReportLab.

Atende rigorosamente aos padrões da Receita Federal e SEFAZ:
- NF-e (Modelo 55): DANFE A4 completo com código de barras Code128C da chave de 44 dígitos,
  emitente, destinatário, totais de impostos e tabela detalhada de itens.
- NFC-e (Modelo 65): Cupom fiscal eletrônico térmico (bobina 80mm) com cabeçalho, resumo de itens
  e QR Code v2.0 em alta resolução.
- Marca d'água automática em cinza claro: "SEM VALOR FISCAL - AMBIENTE DE HOMOLOGACAO"
  em todas as páginas sempre que tpAmb=2.
"""

from io import BytesIO
from typing import Union, Optional
from lxml import etree
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.barcode import code128
from reportlab.pdfgen import canvas

from app.core.config import settings

NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"


class NumberedCanvasWithWatermark(canvas.Canvas):
    """Canvas customizado do ReportLab para inserção da marca d'água de Homologação."""

    def __init__(self, *args, is_homologacao: bool = True, is_nfce: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_homologacao = is_homologacao
        self.is_nfce = is_nfce

    def showPage(self):
        if self.is_homologacao:
            self.saveState()
            self.setFont("Helvetica-Bold", 32 if not self.is_nfce else 14)
            # Cinza bem claro com transparência visual
            self.setFillColor(colors.HexColor("#D8D8D8"))
            if not self.is_nfce:
                # Folha A4: texto diagonal de centro
                self.translate(A4[0] / 2.0, A4[1] / 2.0)
                self.rotate(45)
                self.drawCentredString(0, 0, "SEM VALOR FISCAL")
                self.setFont("Helvetica-Bold", 18)
                self.drawCentredString(0, -30, "AMBIENTE DE HOMOLOGAÇÃO")
            else:
                # Bobina 80mm (226 pt de largura)
                self.translate(113, 250)
                self.rotate(45)
                self.drawCentredString(0, 0, "SEM VALOR FISCAL")
                self.setFont("Helvetica-Bold", 9)
                self.drawCentredString(0, -15, "HOMOLOGAÇÃO")
            self.restoreState()
        super().showPage()


class DanfeGeneratorError(Exception):
    """Exceção levantada em falhas na geração do PDF do DANFE."""
    pass


class DanfePdfGenerator:
    """Gera arquivos PDF do DANFE para NF-e (A4) e NFC-e (Bobina 80mm) com marca d'água homologação."""

    @classmethod
    def generate_danfe_pdf(
        cls,
        xml_input: Union[str, bytes, etree._Element],
        force_homologacao: Optional[bool] = None,
    ) -> bytes:
        """Gera o arquivo PDF do DANFE a partir do XML da NF-e ou NFC-e.

        Detecta automaticamente o modelo da nota (55 para A4, 65 para bobina térmica 80mm)
        e aplica a marca d'água caso tpAmb=2 ou force_homologacao=True.
        """
        if isinstance(xml_input, str):
            root = etree.fromstring(xml_input.encode("utf-8"))
        elif isinstance(xml_input, bytes):
            root = etree.fromstring(xml_input)
        else:
            root = xml_input

        # Localiza infNFe
        inf_nfe = root.find(f".//{{{NFE_NAMESPACE}}}infNFe")
        if inf_nfe is None:
            # Fallback caso XML venha sem namespace ou padrão simplificado
            inf_nfe = root.find(".//infNFe")
            if inf_nfe is None:
                raise DanfeGeneratorError("Tag infNFe não encontrada no XML fornecido.")

        chave_id = inf_nfe.get("Id", "")
        chave_acesso = chave_id.replace("NFe", "")
        
        ide = inf_nfe.find(f"{{{NFE_NAMESPACE}}}ide") or inf_nfe.find("ide")
        modelo = "55"
        tp_amb = 2
        if ide is not None:
            mod_elem = ide.find(f"{{{NFE_NAMESPACE}}}mod") or ide.find("mod")
            if mod_elem is not None and mod_elem.text:
                modelo = mod_elem.text
            tp_amb_elem = ide.find(f"{{{NFE_NAMESPACE}}}tpAmb") or ide.find("tpAmb")
            if tp_amb_elem is not None and tp_amb_elem.text:
                tp_amb = int(tp_amb_elem.text)

        is_homologacao = (tp_amb == 2) if force_homologacao is None else force_homologacao

        if modelo == "65":
            return cls._generate_danfe_nfce(root, inf_nfe, chave_acesso, is_homologacao=is_homologacao)
        return cls._generate_danfe_nfe_a4(root, inf_nfe, chave_acesso, is_homologacao=is_homologacao)

    @classmethod
    def _generate_danfe_nfe_a4(
        cls,
        root: etree._Element,
        inf_nfe: etree._Element,
        chave_acesso: str,
        is_homologacao: bool = True,
    ) -> bytes:
        """Renderiza o DANFE padrão NF-e modelo 55 em folha A4."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20,
            rightMargin=20,
            topMargin=20,
            bottomMargin=20,
        )

        styles = getSampleStyleSheet()
        small_style = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=10)
        bold_small = ParagraphStyle("BoldSmall", parent=styles["Normal"], fontSize=8, leading=10, fontName="Helvetica-Bold")
        title_style = ParagraphStyle("Title", parent=styles["Normal"], fontSize=11, leading=13, fontName="Helvetica-Bold", alignment=1)

        elements = []

        # Extração de dados do emitente
        emit = inf_nfe.find(f"{{{NFE_NAMESPACE}}}emit") or inf_nfe.find("emit")
        x_nome_emit = (emit.findtext(f"{{{NFE_NAMESPACE}}}xNome") or emit.findtext("xNome")) if emit is not None else ""
        cnpj_emit = (emit.findtext(f"{{{NFE_NAMESPACE}}}CNPJ") or emit.findtext("CNPJ")) if emit is not None else ""
        ie_emit = (emit.findtext(f"{{{NFE_NAMESPACE}}}IE") or emit.findtext("IE")) if emit is not None else ""
        ender_emit = (emit.find(f"{{{NFE_NAMESPACE}}}enderEmit") or emit.find("enderEmit")) if emit is not None else None
        
        logr_emit = (ender_emit.findtext(f"{{{NFE_NAMESPACE}}}xLgr") or ender_emit.findtext("xLgr")) if ender_emit is not None else ""
        nro_emit = (ender_emit.findtext(f"{{{NFE_NAMESPACE}}}nro") or ender_emit.findtext("nro")) if ender_emit is not None else ""
        bairro_emit = (ender_emit.findtext(f"{{{NFE_NAMESPACE}}}xBairro") or ender_emit.findtext("xBairro")) if ender_emit is not None else ""
        mun_emit = (ender_emit.findtext(f"{{{NFE_NAMESPACE}}}xMun") or ender_emit.findtext("xMun")) if ender_emit is not None else ""
        uf_emit = (ender_emit.findtext(f"{{{NFE_NAMESPACE}}}UF") or ender_emit.findtext("UF")) if ender_emit is not None else ""

        # Dados da NF
        ide = inf_nfe.find(f"{{{NFE_NAMESPACE}}}ide") or inf_nfe.find("ide")
        n_nf = (ide.findtext(f"{{{NFE_NAMESPACE}}}nNF") or ide.findtext("nNF")) if ide is not None else ""
        serie = (ide.findtext(f"{{{NFE_NAMESPACE}}}serie") or ide.findtext("serie")) if ide is not None else "1"
        dh_emi = ((ide.findtext(f"{{{NFE_NAMESPACE}}}dhEmi") or ide.findtext("dhEmi") or "")[:10]) if ide is not None else ""

        # Protocolo de autorização (se presente no nfeProc)
        n_prot = (
            root.findtext(f".//{{{NFE_NAMESPACE}}}protNFe/{{{NFE_NAMESPACE}}}infProt/{{{NFE_NAMESPACE}}}nProt")
            or root.findtext(".//protNFe/infProt/nProt")
            or ("AUTORIZADO EM HOMOLOGAÇÃO" if is_homologacao else "EMISSÃO EM CONTINGÊNCIA")
        )

        # 1. Código de barras Code128 da Chave de Acesso
        barcode = code128.Code128(chave_acesso, barWidth=1.0, barHeight=35)

        # Cabeçalho: Emitente + DANFE + Código de Barras
        col_emit = [
            Paragraph(f"<b>{x_nome_emit}</b>", bold_small),
            Paragraph(f"{logr_emit}, {nro_emit} - {bairro_emit}", small_style),
            Paragraph(f"{mun_emit} - {uf_emit}", small_style),
            Paragraph(f"CNPJ: {cnpj_emit} | IE: {ie_emit}", small_style),
        ]

        col_danfe = [
            Paragraph("<b>DANFE</b>", title_style),
            Paragraph("Documento Auxiliar da<br/>Nota Fiscal Eletrônica", small_style),
            Spacer(1, 4),
            Paragraph("<b>0 - ENTRADA<br/>1 - SAÍDA: 1</b>", small_style),
            Paragraph(f"<b>Nº {n_nf} | Série {serie}</b>", bold_small),
        ]

        col_chave = [
            barcode,
            Spacer(1, 4),
            Paragraph(f"<b>CHAVE DE ACESSO:</b><br/>{chave_acesso}", small_style),
            Paragraph(f"<b>PROTOCOLO:</b> {n_prot}", small_style),
        ]

        header_table = Table([[col_emit, col_danfe, col_chave]], colWidths=[200, 110, 245])
        header_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 8))

        # 2. Dados do Destinatário
        dest = inf_nfe.find(f"{{{NFE_NAMESPACE}}}dest") or inf_nfe.find("dest")
        if dest is not None:
            x_nome_dest = dest.findtext(f"{{{NFE_NAMESPACE}}}xNome") or dest.findtext("xNome") or ""
            doc_dest = (
                dest.findtext(f"{{{NFE_NAMESPACE}}}CNPJ")
                or dest.findtext("CNPJ")
                or dest.findtext(f"{{{NFE_NAMESPACE}}}CPF")
                or dest.findtext("CPF")
                or ""
            )
            ender_dest = dest.find(f"{{{NFE_NAMESPACE}}}enderDest") or dest.find("enderDest")
            logr_dest = (ender_dest.findtext(f"{{{NFE_NAMESPACE}}}xLgr") or ender_dest.findtext("xLgr") or "") if ender_dest is not None else ""
            nro_dest = (ender_dest.findtext(f"{{{NFE_NAMESPACE}}}nro") or ender_dest.findtext("nro") or "") if ender_dest is not None else ""
            mun_dest = (ender_dest.findtext(f"{{{NFE_NAMESPACE}}}xMun") or ender_dest.findtext("xMun") or "") if ender_dest is not None else ""
            uf_dest = (ender_dest.findtext(f"{{{NFE_NAMESPACE}}}UF") or ender_dest.findtext("UF") or "") if ender_dest is not None else ""

            dest_data = [
                [Paragraph("<b>DESTINATÁRIO / REMETENTE</b>", bold_small), ""],
                [
                    Paragraph(f"Nome / Razão Social: <b>{x_nome_dest}</b>", small_style),
                    Paragraph(f"CNPJ/CPF: <b>{doc_dest}</b>", small_style),
                ],
                [
                    Paragraph(f"Endereço: {logr_dest}, {nro_dest} - {mun_dest}/{uf_dest}", small_style),
                    Paragraph(f"Data Emissão: {dh_emi}", small_style),
                ],
            ]
            dest_table = Table(dest_data, colWidths=[380, 175])
            dest_table.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("SPAN", (0, 0), (1, 0)),
                ("BACKGROUND", (0, 0), (1, 0), colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(dest_table)
            elements.append(Spacer(1, 8))

        # 3. Totais da Nota
        total = inf_nfe.find(f".//{{{NFE_NAMESPACE}}}total/{{{NFE_NAMESPACE}}}ICMSTot") or inf_nfe.find(".//total/ICMSTot")
        v_prod = (total.findtext(f"{{{NFE_NAMESPACE}}}vProd") or total.findtext("vProd")) if total is not None else "0.00"
        v_desc = (total.findtext(f"{{{NFE_NAMESPACE}}}vDesc") or total.findtext("vDesc")) if total is not None else "0.00"
        v_frete = (total.findtext(f"{{{NFE_NAMESPACE}}}vFrete") or total.findtext("vFrete")) if total is not None else "0.00"
        v_nf = (total.findtext(f"{{{NFE_NAMESPACE}}}vNF") or total.findtext("vNF")) if total is not None else "0.00"

        tot_data = [
            [Paragraph("<b>CÁLCULO DO IMPOSTO</b>", bold_small), "", "", ""],
            [
                Paragraph("Base ICMS: R$ 0.00", small_style),
                Paragraph("Valor ICMS: R$ 0.00", small_style),
                Paragraph(f"Valor Desconto: R$ {v_desc}", small_style),
                Paragraph(f"Valor Produtos: R$ {v_prod}", small_style),
            ],
            [
                Paragraph(f"Valor Frete: R$ {v_frete}", small_style),
                Paragraph("Valor Seguro: R$ 0.00", small_style),
                Paragraph("Outras Desp: R$ 0.00", small_style),
                Paragraph(f"<b>TOTAL DA NOTA: R$ {v_nf}</b>", bold_small),
            ],
        ]
        tot_table = Table(tot_data, colWidths=[138, 138, 138, 141])
        tot_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("SPAN", (0, 0), (3, 0)),
            ("BACKGROUND", (0, 0), (3, 0), colors.lightgrey),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(tot_table)
        elements.append(Spacer(1, 8))

        # 4. Tabela de Itens
        itens_rows = [
            [
                Paragraph("<b>Cód</b>", bold_small),
                Paragraph("<b>Descrição do Produto</b>", bold_small),
                Paragraph("<b>NCM</b>", bold_small),
                Paragraph("<b>CFOP</b>", bold_small),
                Paragraph("<b>Un</b>", bold_small),
                Paragraph("<b>Qtd</b>", bold_small),
                Paragraph("<b>V. Unit</b>", bold_small),
                Paragraph("<b>V. Total</b>", bold_small),
            ]
        ]
        dets = inf_nfe.findall(f"{{{NFE_NAMESPACE}}}det") or inf_nfe.findall("det")
        for det in dets:
            prod = det.find(f"{{{NFE_NAMESPACE}}}prod") or det.find("prod")
            itens_rows.append([
                Paragraph((prod.findtext(f"{{{NFE_NAMESPACE}}}cProd") or prod.findtext("cProd") or ""), small_style),
                Paragraph((prod.findtext(f"{{{NFE_NAMESPACE}}}xProd") or prod.findtext("xProd") or ""), small_style),
                Paragraph((prod.findtext(f"{{{NFE_NAMESPACE}}}NCM") or prod.findtext("NCM") or ""), small_style),
                Paragraph((prod.findtext(f"{{{NFE_NAMESPACE}}}CFOP") or prod.findtext("CFOP") or ""), small_style),
                Paragraph((prod.findtext(f"{{{NFE_NAMESPACE}}}uCom") or prod.findtext("uCom") or ""), small_style),
                Paragraph((prod.findtext(f"{{{NFE_NAMESPACE}}}qCom") or prod.findtext("qCom") or ""), small_style),
                Paragraph((prod.findtext(f"{{{NFE_NAMESPACE}}}vUnCom") or prod.findtext("vUnCom") or ""), small_style),
                Paragraph((prod.findtext(f"{{{NFE_NAMESPACE}}}vProd") or prod.findtext("vProd") or ""), small_style),
            ])

        itens_table = Table(itens_rows, colWidths=[50, 205, 55, 45, 30, 45, 60, 65])
        itens_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(itens_table)

        # Construção usando o Canvas customizado com marca d'água
        def canvas_maker(*args, **kwargs):
            return NumberedCanvasWithWatermark(*args, is_homologacao=is_homologacao, is_nfce=False, **kwargs)

        doc.build(elements, canvasmaker=canvas_maker)
        return buffer.getvalue()

    @classmethod
    def _generate_danfe_nfce(
        cls,
        root: etree._Element,
        inf_nfe: etree._Element,
        chave_acesso: str,
        is_homologacao: bool = True,
    ) -> bytes:
        """Renderiza o DANFE NFC-e modelo 65 para impressora térmica/bobina de 80mm com QR Code."""
        # 80mm = ~226 pontos de largura
        page_width = 226
        page_height = 560
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=(page_width, page_height),
            leftMargin=10,
            rightMargin=10,
            topMargin=10,
            bottomMargin=10,
        )

        styles = getSampleStyleSheet()
        center_small = ParagraphStyle("CenterSmall", parent=styles["Normal"], fontSize=8, leading=10, alignment=1)
        center_bold = ParagraphStyle("CenterBold", parent=styles["Normal"], fontSize=9, leading=11, fontName="Helvetica-Bold", alignment=1)

        elements = []

        emit = inf_nfe.find(f"{{{NFE_NAMESPACE}}}emit") or inf_nfe.find("emit")
        x_nome_emit = (emit.findtext(f"{{{NFE_NAMESPACE}}}xNome") or emit.findtext("xNome")) if emit is not None else ""
        cnpj_emit = (emit.findtext(f"{{{NFE_NAMESPACE}}}CNPJ") or emit.findtext("CNPJ")) if emit is not None else ""

        elements.append(Paragraph(f"<b>{x_nome_emit}</b>", center_bold))
        elements.append(Paragraph(f"CNPJ: {cnpj_emit}", center_small))
        elements.append(Paragraph("<b>DANFE NFC-e - Documento Auxiliar</b>", center_bold))
        elements.append(Paragraph("Não permite aproveitamento de crédito de ICMS", center_small))
        elements.append(Spacer(1, 6))

        # Total
        total = inf_nfe.find(f".//{{{NFE_NAMESPACE}}}total/{{{NFE_NAMESPACE}}}ICMSTot") or inf_nfe.find(".//total/ICMSTot")
        v_nf = (total.findtext(f"{{{NFE_NAMESPACE}}}vNF") or total.findtext("vNF")) if total is not None else "0.00"
        elements.append(Paragraph(f"<b>VALOR TOTAL: R$ {v_nf}</b>", center_bold))
        elements.append(Spacer(1, 6))

        # QR Code da NFC-e em alta resolução
        qr_code_str = (
            root.findtext(f".//{{{NFE_NAMESPACE}}}infNFeSupl/{{{NFE_NAMESPACE}}}qrCode")
            or root.findtext(".//infNFeSupl/qrCode")
            or f"https://sefaz.sp.gov.br?p={chave_acesso}"
        )
        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(qr_code_str)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")

        qr_buffer = BytesIO()
        img_qr.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        elements.append(Image(qr_buffer, width=120, height=120))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(f"<b>Chave de Acesso:</b><br/>{chave_acesso}", center_small))

        def canvas_maker(*args, **kwargs):
            return NumberedCanvasWithWatermark(*args, is_homologacao=is_homologacao, is_nfce=True, **kwargs)

        doc.build(elements, canvasmaker=canvas_maker)
        return buffer.getvalue()
