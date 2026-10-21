"""Gerador de QR Code v2.0 para NFC-e (Nota Fiscal de Consumidor Eletrônica - Modelo 65).

Segue a especificação técnica do Manual de Padrões Técnicos do DANFE NFC-e e QR Code:
Estrutura do Parâmetro de Consulta (v2.0):
    chNFe|2|tpAmb|cIdToken
    (ou chNFe|2|tpAmb|cDest|vNF|vICMS|digVal|cIdToken quando em contingência offline)
Cálculo do Hash SHA-1:
    hash = SHA1(parametros + CSC_TOKEN) em formato hexadecimal MAIÚSCULO.
String final do QR Code:
    urlConsulta?p=parametros|hash
"""

from typing import Union
import hashlib
from lxml import etree

from app.core.config import settings
from app.core.uf_matrix import get_nfce_qr_code_url


NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"


class QRCodeGeneratorError(Exception):
    """Exceção levantada em caso de inconsistência na geração do QR Code."""
    pass


class QRCodeGenerator:
    """Calcula e injeta a URL e o payload de QR Code v2.0 no XML da NFC-e."""

    @classmethod
    def generate_qr_code_v2(
        cls,
        chave_acesso: str,
        tp_amb: int,
        c_id_token: str,
        csc_token: str,
        url_consulta: str,
    ) -> str:
        """Gera a URL completa contendo o parâmetro p com o hash SHA-1 do QR Code v2.0 (emissão normal).

        Args:
            chave_acesso: Chave de 44 dígitos da NFC-e.
            tp_amb: 1 para Produção, 2 para Homologação.
            c_id_token: Identificador do CSC (ex: '000001').
            csc_token: Código alfanumérico do CSC (ex: '0123456789ABCDEF').
            url_consulta: URL base da SEFAZ para consulta da NFC-e da UF.

        Returns:
            str: URL com parâmetro p contendo dados e hash SHA-1 maiúsculo.
        """
        if not csc_token:
            raise QRCodeGeneratorError("Token do CSC (CSC_TOKEN) não informado para o ambiente.")

        if not c_id_token:
            raise QRCodeGeneratorError("Identificador do CSC (CSC_ID / cIdToken) não informado.")

        # Remove zeros à esquerda do cIdToken se necessário ou formata com int
        c_id_token_fmt = str(int(c_id_token))

        # Versão do QR Code: 2 (SEFAZ v2.0)
        versao_qr = "2"

        # Montagem dos parâmetros: chNFe|2|tpAmb|cIdToken
        payload_base = f"{chave_acesso}|{versao_qr}|{tp_amb}|{c_id_token_fmt}"

        # Concatenação dos parâmetros com o CSC: payload + CSC_TOKEN
        payload_to_hash = f"{payload_base}{csc_token}"

        # Hash SHA-1 em hexadecimal maiúsculo
        sha1_hash = hashlib.sha1(payload_to_hash.encode("ascii")).hexdigest().upper()

        # String final do parâmetro p
        param_p = f"{payload_base}|{sha1_hash}"

        sep = "&" if "?" in url_consulta else "?"
        return f"{url_consulta}{sep}p={param_p}"

    @classmethod
    def inject_qr_code_into_xml(
        cls,
        xml_input: Union[bytes, str, etree._Element],
        uf_emitente: str,
        is_production: Optional[bool] = None,
        c_id_token: Optional[str] = None,
        csc_token: Optional[str] = None,
    ) -> etree._Element:
        """Calcula e injeta os nós infNFeSupl/qrCode e infNFeSupl/urlChave na árvore XML da NFC-e.

        Args:
            xml_input: Documento XML assinado ou em construção.
            uf_emitente: Sigla da UF do emitente (ex: 'SP', 'BA').
            is_production: Se None, utiliza settings.is_production.
            c_id_token: Se None, utiliza settings.active_csc_id.
            csc_token: Se None, utiliza settings.active_csc_token.

        Returns:
            etree._Element: Elemento raiz com o nó infNFeSupl atualizado.
        """
        if isinstance(xml_input, str):
            root = etree.fromstring(xml_input.encode("utf-8"))
        elif isinstance(xml_input, bytes):
            root = etree.fromstring(xml_input)
        else:
            root = xml_input

        # Extrai infNFe
        inf_nfe = root.find(f".//{{{NFE_NAMESPACE}}}infNFe")
        if inf_nfe is None:
            raise QRCodeGeneratorError("Tag 'infNFe' não encontrada no XML da NFC-e.")

        chave_id = inf_nfe.get("Id", "")
        chave_acesso = chave_id.replace("NFe", "")
        if len(chave_acesso) != 44:
            raise QRCodeGeneratorError(f"Chave de acesso inválida em infNFe Id='{chave_id}'.")

        is_prod = is_production if is_production is not None else settings.is_production
        tp_amb = 1 if is_prod else 2

        active_id = c_id_token or settings.active_csc_id
        active_token = csc_token or settings.active_csc_token
        url_base = get_nfce_qr_code_url(uf_emitente, is_production=is_prod)

        qr_code_url = cls.generate_qr_code_v2(
            chave_acesso=chave_acesso,
            tp_amb=tp_amb,
            c_id_token=active_id,
            csc_token=active_token,
            url_consulta=url_base,
        )

        # Localiza ou cria infNFeSupl
        supl = root.find(f"{{{NFE_NAMESPACE}}}infNFeSupl")
        if supl is None:
            supl = etree.SubElement(root, f"{{{NFE_NAMESPACE}}}infNFeSupl")

        # Atualiza qrCode
        qr_el = supl.find(f"{{{NFE_NAMESPACE}}}qrCode")
        if qr_el is None:
            qr_el = etree.SubElement(supl, f"{{{NFE_NAMESPACE}}}qrCode")
        qr_el.text = qr_code_url

        # Atualiza urlChave
        url_el = supl.find(f"{{{NFE_NAMESPACE}}}urlChave")
        if url_el is None:
            url_el = etree.SubElement(supl, f"{{{NFE_NAMESPACE}}}urlChave")
        url_el.text = url_base

        return root
