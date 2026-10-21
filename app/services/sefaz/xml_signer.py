"""Assinador Digital XML padrão W3C XML-DSig ICP-Brasil para SEFAZ (NF-e 55 e NFC-e 65).

Segue rigorosamente a especificação do Manual de Orientação do Contribuinte (MOC 7.0):
- Canonicalização: http://www.w3.org/TR/2001/REC-xml-c14n-20010315 (C14N)
- Algoritmo de Assinatura: http://www.w3.org/2000/09/xmldsig#rsa-sha1
- Algoritmo de Digest: http://www.w3.org/2000/09/xmldsig#sha1
- Transformações: Enveloped Signature e C14N
"""

from typing import Union
import base64
from lxml import etree

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from app.core.security.certificate import A1CertificateManager


DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
C14N_ALGORITHM = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA1_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
SHA1_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#sha1"
ENVELOPED_SIGNATURE = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"


class XmlSignerError(Exception):
    """Exceção levantada quando ocorre erro durante o processo de assinatura digital."""
    pass


class XmlSigner:
    """Responsável pela assinatura digital XML-DSig de documentos fiscais eletrônicos."""

    def __init__(self, cert_manager: A1CertificateManager):
        self.cert_manager = cert_manager

    def sign(
        self,
        xml_input: Union[bytes, str, etree._Element],
        reference_tag: str = "infNFe",
    ) -> etree._Element:
        """Assina digitalmente um XML contendo a tag de referência (ex: infNFe).

        Args:
            xml_input: Documento XML em bytes, string ou etree._Element.
            reference_tag: Nome da tag a ser assinada (padrão: 'infNFe').

        Returns:
            etree._Element: Elemento raiz com o bloco <Signature> injetado.
        """
        if isinstance(xml_input, str):
            root = etree.fromstring(xml_input.encode("utf-8"))
        elif isinstance(xml_input, bytes):
            root = etree.fromstring(xml_input)
        else:
            root = xml_input

        # 1. Localiza o elemento a ser assinado (infNFe)
        target_element = root.find(f".//{{*}}{reference_tag}")
        if target_element is None:
            raise XmlSignerError(f"Tag de referência '{reference_tag}' não encontrada no XML fornecido.")

        ref_id = target_element.get("Id")
        if not ref_id:
            raise XmlSignerError(f"Tag de referência '{reference_tag}' não possui atributo 'Id'.")

        # 2. Canonicalização (C14N) do nó infNFe
        c14n_target = etree.tostring(
            target_element,
            method="c14n",
            exclusive=False,
            with_comments=False,
        )

        # 3. Cálculo do DigestValue (SHA-1) sobre a tag canonicalizada
        digest = hashes.Hash(hashes.SHA1())
        digest.update(c14n_target)
        digest_bytes = digest.finalize()
        digest_value_b64 = base64.b64encode(digest_bytes).decode("ascii")

        # 4. Construção da estrutura <SignedInfo>
        signed_info = etree.Element(f"{{{DSIG_NS}}}SignedInfo", nsmap={None: DSIG_NS})

        c14n_method = etree.SubElement(signed_info, f"{{{DSIG_NS}}}CanonicalizationMethod")
        c14n_method.set("Algorithm", C14N_ALGORITHM)

        sig_method = etree.SubElement(signed_info, f"{{{DSIG_NS}}}SignatureMethod")
        sig_method.set("Algorithm", RSA_SHA1_ALGORITHM)

        reference = etree.SubElement(signed_info, f"{{{DSIG_NS}}}Reference")
        reference.set("URI", f"#{ref_id}")

        transforms = etree.SubElement(reference, f"{{{DSIG_NS}}}Transforms")

        trans_env = etree.SubElement(transforms, f"{{{DSIG_NS}}}Transform")
        trans_env.set("Algorithm", ENVELOPED_SIGNATURE)

        trans_c14n = etree.SubElement(transforms, f"{{{DSIG_NS}}}Transform")
        trans_c14n.set("Algorithm", C14N_ALGORITHM)

        digest_method = etree.SubElement(reference, f"{{{DSIG_NS}}}DigestMethod")
        digest_method.set("Algorithm", SHA1_ALGORITHM)

        digest_val_el = etree.SubElement(reference, f"{{{DSIG_NS}}}DigestValue")
        digest_val_el.text = digest_value_b64

        # 7. Construção do nó <Signature> completo
        signature = etree.Element(f"{{{DSIG_NS}}}Signature", nsmap={None: DSIG_NS})
        signature.append(signed_info)

        # 5. Canonicalização (C14N) do nó <SignedInfo> exatamente na sua árvore definitiva
        c14n_signed_info = etree.tostring(
            signed_info,
            method="c14n",
            exclusive=False,
            with_comments=False,
        )

        # 6. Assinatura RSA-SHA1 com a chave privada do certificado A1
        private_key = self.cert_manager.private_key
        signature_bytes = private_key.sign(
            c14n_signed_info,
            padding.PKCS1v15(),
            hashes.SHA1(),
        )
        signature_value_b64 = base64.b64encode(signature_bytes).decode("ascii")

        sig_val_el = etree.SubElement(signature, f"{{{DSIG_NS}}}SignatureValue")
        sig_val_el.text = signature_value_b64

        key_info = etree.SubElement(signature, f"{{{DSIG_NS}}}KeyInfo")
        x509_data = etree.SubElement(key_info, f"{{{DSIG_NS}}}X509Data")
        x509_cert = etree.SubElement(x509_data, f"{{{DSIG_NS}}}X509Certificate")

        # Certificado X.509 em Base64 (formato limpo exigido pela SEFAZ)
        cert_der = self.cert_manager.certificate.public_bytes(
            encoding=serialization.Encoding.DER
        )
        x509_cert.text = base64.b64encode(cert_der).decode("ascii")

        # 8. Injeta o bloco <Signature> logo após a tag referenciada (ex: infNFe)
        target_parent = target_element.getparent()
        target_idx = target_parent.index(target_element)
        target_parent.insert(target_idx + 1, signature)

        return root

    def sign_to_xml_bytes(
        self,
        xml_input: Union[bytes, str, etree._Element],
        reference_tag: str = "infNFe",
        pretty_print: bool = False,
    ) -> bytes:
        """Assina e retorna o XML em bytes UTF-8."""
        signed_root = self.sign(xml_input, reference_tag)
        return etree.tostring(
            signed_root,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=pretty_print,
        )
