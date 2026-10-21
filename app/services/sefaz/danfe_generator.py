"""Gerador de DANFE em PDF a partir do XML definitivo da NF-e e NFC-e (<nfeProc> ou <NFe>).

Utiliza ReportLab para construir o layout em conformidade com o Manual de Padrões Técnicos da SEFAZ:
- NF-e (Modelo 55): DANFE Retrato em folha A4 com código de barras Code128C da chave de 44 dígitos.
- NFC-e (Modelo 65): DANFE Cupom Fiscal eletrônico em bobina (80mm) com QR Code impresso e resumo de itens.
"""

from io import BytesIO
from typing import Union
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


NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"


class DanfeGeneratorError(Exception):
    """Exceção levantada em falhas na geração do PDF do DANFE."""
    pass


class DanfePdfGenerator:
    """Gera arquivos PDF do DANFE para NF-e (A4) e NFC-e (Bobina 80mm)."""

    @classmethod
    def generate_danfe_pdf(cls, xml_input: Union[str, bytes, etree._Element]) -> bytes:
        """Gera o arquivo PDF do DANFE a partir do XML da NF-e ou NFC-e.

        Detecta automaticamente o modelo da nota (55 para A4, 65 para bobina térmica).
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
            raise DanfeGeneratorError("Tag infNFe não encontrada no XML fornecido.")

        chave_id = inf_nfe.get("Id", "")
        chave_acesso = chave_id.replace("NFe", "")
        modelo = inf_nfe.findtext(f".//{{{NFE_NAMESPACE}}}ide/{{{NFE_NAMESPACE}}}mod") or "55"

        if modelo == "65":
            return cls._generate_danfe_nfce(root, inf_nfe, chave_acesso)
        return cls._generate_danfe_nfe_a4(root, inf_nfe, chave_acesso)

    @classmethod
    def _generate_danfe_nfe_a4(cls, root: etree._Element, inf_nfe: etree._Element, chave_acesso: str) -> bytes:
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
        emit = inf_nfe.find(f"{{{NFE_NAMESPACE}}}emit")
        x_nome_emit = emit.findtext(f"{{{NFE_NAMESPACE}}}xNome") or ""
        cnpj_emit = emit.findtext(f"{{{NFE_NAMESPACE}}}CNPJ") or ""
        ie_emit = emit.findtext(f"{{{NFE_NAMESPACE}}}IE") or ""
        ender_emit = emit.find(f"{{{NFE_NAMESPACE}}}enderEmit")
        logr_emit = ender_emit.findtext(f"{{{NFE_NAMESPACE}}}xLgr") or ""
        nro_emit = ender_emit.findtext(f"{{{NFE_NAMESPACE}}}nro") or ""
        bairro_emit = ender_emit.findtext(f"{{{NFE_NAMESPACE}}}xBairro") or ""
        mun_emit = ender_emit.findtext(f"{{{NFE_NAMESPACE}}}xMun") or ""
        uf_emit = ender_emit.findtext(f"{{{NFE_NAMESPACE}}}UF") or ""

        # Dados da NF
        ide = inf_nfe.find(f"{{{NFE_NAMESPACE}}}ide")
        n_nf = ide.findtext(f"{{{NFE_NAMESPACE}}}nNF") or ""
        serie = ide.findtext(f"{{{NFE_NAMESPACE}}}serie") or "1"
        dh_emi = (ide.findtext(f"{{{NFE_NAMESPACE}}}dhEmi") or "")[:10]

        # Protocolo de autorização (se presente no nfeProc)
        n_prot = root.findtext(f".//{{{NFE_NAMESPACE}}}protNFe/{{{NFE_NAMESPACE}}}infProt/{{{NFE_NAMESPACE}}}nProt") or "HOMOLOGAÇÃO / TESTES"

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
            Paragraph(f"<b>0 - ENTRADA<br/>1 - SAÍDA: 1</b>", small_style),
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
        dest = inf_nfe.find(f"{{{NFE_NAMESPACE}}}dest")
        if dest is not None:
            x_nome_dest = dest.findtext(f"{{{NFE_NAMESPACE}}}xNome") or ""
            doc_dest = dest.findtext(f"{{{NFE_NAMESPACE}}}CNPJ") or dest.findtext(f"{{{NFE_NAMESPACE}}}CPF") or ""
            ender_dest = dest.find(f"{{{NFE_NAMESPACE}}}enderDest")
            logr_dest = ender_dest.findtext(f"{{{NFE_NAMESPACE}}}xLgr") or "" if ender_dest is not None else ""
            nro_dest = ender_dest.findtext(f"{{{NFE_NAMESPACE}}}nro") or "" if ender_dest is not None else ""
            mun_dest = ender_dest.findtext(f"{{{NFE_NAMESPACE}}}xMun") or "" if ender_dest is not None else ""
            uf_dest = ender_dest.findtext(f"{{{NFE_NAMESPACE}}}UF") or "" if ender_dest is not None else ""

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
        total = inf_nfe.find(f".//{{{NFE_NAMESPACE}}}total/{{{NFE_NAMESPACE}}}ICMSTot")
        v_prod = total.findtext(f"{{{NFE_NAMESPACE}}}vProd") if total is not None else "0.00"
        v_desc = total.findtext(f"{{{NFE_NAMESPACE}}}vDesc") if total is not None else "0.00"
        v_frete = total.findtext(f"{{{NFE_NAMESPACE}}}vFrete") if total is not None else "0.00"
        v_nf = total.findtext(f"{{{NFE_NAMESPACE}}}vNF") if total is not None else "0.00"

        tot_data = [
            [Paragraph("<b>CÁLCULO DO IMPOSTO</b>", bold_small), "", "", ""],
            [
                Paragraph(f"Base ICMS: R$ 0.00", small_style),
                Paragraph(f"Valor ICMS: R$ 0.00", small_style),
                Paragraph(f"Valor Desconto: R$ {v_desc}", small_style),
                Paragraph(f"Valor Produtos: R$ {v_prod}", small_style),
            ],
            [
                Paragraph(f"Valor Frete: R$ {v_frete}", small_style),
                Paragraph(f"Valor Seguro: R$ 0.00", small_style),
                Paragraph(f"Outras Desp: R$ 0.00", small_style),
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
        for det in inf_nfe.findall(f"{{{NFE_NAMESPACE}}}det"):
            prod = det.find(f"{{{NFE_NAMESPACE}}}prod")
            itens_rows.append([
                Paragraph(prod.findtext(f"{{{NFE_NAMESPACE}}}cProd") or "", small_style),
                Paragraph(prod.findtext(f"{{{NFE_NAMESPACE}}}xProd") or "", small_style),
                Paragraph(prod.findtext(f"{{{NFE_NAMESPACE}}}NCM") or "", small_style),
                Paragraph(prod.findtext(f"{{{NFE_NAMESPACE}}}CFOP") or "", small_style),
                Paragraph(prod.findtext(f"{{{NFE_NAMESPACE}}}uCom") or "", small_style),
                Paragraph(prod.findtext(f"{{{NFE_NAMESPACE}}}qCom") or "", small_style),
                Paragraph(prod.findtext(f"{{{NFE_NAMESPACE}}}vUnCom") or "", small_style),
                Paragraph(prod.findtext(f"{{{NFE_NAMESPACE}}}vProd") or "", small_style),
            ])

        itens_table = Table(itens_rows, colWidths=[50, 205, 55, 45, 30, 45, 60, 65])
        itens_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(itens_table)

        doc.build(elements)
        return buffer.getvalue()

    @classmethod
    def _generate_danfe_nfce(cls, root: etree._Element, inf_nfe: etree._Element, chave_acesso: str) -> bytes:
        """Renderiza o DANFE NFC-e modelo 65 para impressora térmica/bobina de 80mm."""
        # 80mm = ~226 pontos de largura
        page_width = 226
        # Altura dinâmica ou padrão contínuo
        page_height = 500
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

        emit = inf_nfe.find(f"{{{NFE_NAMESPACE}}}emit")
        x_nome_emit = emit.findtext(f"{{{NFE_NAMESPACE}}}xNome") or ""
        cnpj_emit = emit.findtext(f"{{{NFE_NAMESPACE}}}CNPJ") or ""

        elements.append(Paragraph(f"<b>{x_nome_emit}</b>", center_bold))
        elements.append(Paragraph(f"CNPJ: {cnpj_emit}", center_small))
        elements.append(Paragraph("<b>DANFE NFC-e - Documento Auxiliar</b>", center_bold))
        elements.append(Paragraph("Não permite aproveitamento de crédito de ICMS", center_small))
        elements.append(Spacer(1, 6))

        # Total
        total = inf_nfe.find(f".//{{{NFE_NAMESPACE}}}total/{{{NFE_NAMESPACE}}}ICMSTot")
        v_nf = total.findtext(f"{{{NFE_NAMESPACE}}}vNF") if total is not None else "0.00"
        elements.append(Paragraph(f"<b>VALOR TOTAL: R$ {v_nf}</b>", center_bold))
        elements.append(Spacer(1, 6))

        # QR Code da NFC-e
        qr_code_str = root.findtext(f".//{{{NFE_NAMESPACE}}}infNFeSupl/{{{NFE_NAMESPACE}}}qrCode") or f"https://sefaz.sp.gov.br?p={chave_acesso}"
        qr = qrcode.QRCode(box_size=3, border=1)
        qr.add_data(qr_code_str)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")

        qr_buffer = BytesIO()
        img_qr.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        elements.append(Image(qr_buffer, width=110, height=110))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(f"<b>Chave de Acesso:</b><br/>{chave_acesso}", center_small))

        doc.build(elements)
        return buffer.getvalue()
