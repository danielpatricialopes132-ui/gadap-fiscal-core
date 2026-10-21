"""Testes unitários para Assinatura Digital XML-DSig ICP-Brasil e Gerador de QR Code v2.0 (NFC-e)."""

from decimal import Decimal
import base64
import hashlib
import pytest
from lxml import etree

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

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
from app.services.sefaz.xml_builder import NFeXmlBuilder, NFE_NAMESPACE
from app.services.sefaz.xml_signer import XmlSigner, DSIG_NS, XmlSignerError
from app.services.sefaz.qrcode_generator import QRCodeGenerator
from app.core.security.certificate import A1CertificateManager
from tests.test_certificate import generate_self_signed_pfx


@pytest.fixture
def cert_manager() -> A1CertificateManager:
    password = "signer_password"
    pfx_data = generate_self_signed_pfx(
        common_name="EMITENTE TESTE LTDA:12345678000195",
        password=password,
    )
    return A1CertificateManager(pfx_data=pfx_data, password=password)


@pytest.fixture
def sample_nfe_doc() -> DocumentoFiscalInput:
    emitente = EmitenteInput(
        cnpj="12345678000195",
        razao_social="EMITENTE PAULISTA LTDA",
        ie="123456789110",
        crt="1",
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

    destinatario = DestinatarioInput(
        cpf_cnpj="01234567890",
        razao_social="JOAO DA SILVA",
        ind_iedest="9",
        endereco=EnderecoInput(
            logradouro="Rua Augusta",
            numero="200",
            bairro="Cerqueira Cesar",
            codigo_municipio="3550308",
            nome_municipio="Sao Paulo",
            uf="SP",
            cep="01412000",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="CABO01",
        descricao="Cabo de Rede Cat6",
        ncm="85444200",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("35.00"),
        csosn="102",
    )

    return DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFE,
        numero=777,
        serie=1,
        emitente=emitente,
        destinatario=destinatario,
        itens=[item],
        pagamentos=[PagamentoInput(forma=FormaPagamento.PIX, valor=Decimal("35.00"))],
    )


def test_xml_signer_full_pipeline(cert_manager, sample_nfe_doc):
    """Valida a assinatura XML-DSig completa, C14N, Digest SHA-1 e SignatureValue."""
    doc_proc = TaxEngineSimplesNacional.process(sample_nfe_doc)
    builder = NFeXmlBuilder(doc_proc, c_nf="12345678")
    raw_xml_element = builder.build()

    signer = XmlSigner(cert_manager)
    signed_element = signer.sign(raw_xml_element)

    # 1. Verifica presença do bloco <Signature>
    sig = signed_element.find(f"{{{DSIG_NS}}}Signature")
    assert sig is not None, "Bloco <Signature> deve estar presente no nó raiz"

    # 2. Verifica estrutura do SignedInfo
    signed_info = sig.find(f"{{{DSIG_NS}}}SignedInfo")
    assert signed_info is not None

    ref = signed_info.find(f"{{{DSIG_NS}}}Reference")
    assert ref is not None
    assert ref.get("URI") == f"#NFe{builder.chave_acesso}"

    # 3. Valida integridade matemática do DigestValue (SHA-1 de infNFe C14N)
    inf_nfe = signed_element.find(f".//{{{NFE_NAMESPACE}}}infNFe")
    c14n_inf_nfe = etree.tostring(inf_nfe, method="c14n", exclusive=False, with_comments=False)

    digest_calculado = hashlib.sha1(c14n_inf_nfe).digest()
    digest_esperado = base64.b64decode(ref.find(f"{{{DSIG_NS}}}DigestValue").text)
    assert digest_calculado == digest_esperado, "DigestValue não confere com o hash SHA-1 de infNFe"

    # 4. Valida integridade criptográfica do SignatureValue com a chave pública
    sig_value_b64 = sig.find(f"{{{DSIG_NS}}}SignatureValue").text
    sig_bytes = base64.b64decode(sig_value_b64)

    c14n_signed_info = etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False)
    public_key = cert_manager.certificate.public_key()

    # public_key.verify não deve levantar exceção se a assinatura for válida
    public_key.verify(
        sig_bytes,
        c14n_signed_info,
        padding.PKCS1v15(),
        hashes.SHA1(),
    )

    # 5. Verifica certificado público em X509Certificate
    x509_cert_el = sig.find(f".//{{{DSIG_NS}}}X509Certificate")
    assert x509_cert_el is not None
    assert len(x509_cert_el.text) > 100


def test_qrcode_generator_v2_sha1_hash():
    """Valida o cálculo do hash SHA-1 maiúsculo no QR Code v2.0 da NFC-e."""
    chave = "35261012345678000195650010000008881112233445"
    tp_amb = 2
    c_id_token = "000001"
    csc_token = "0123456789ABCDEF"
    url_base = "https://www.homologacao.nfce.fazenda.sp.gov.br/qrcode"

    qr_url = QRCodeGenerator.generate_qr_code_v2(
        chave_acesso=chave,
        tp_amb=tp_amb,
        c_id_token=c_id_token,
        csc_token=csc_token,
        url_consulta=url_base,
    )

    # Formato esperado: url?p=chave|2|tpAmb|1|HASH
    assert "?p=" in qr_url
    param_p = qr_url.split("?p=")[1]
    partes = param_p.split("|")

    assert partes[0] == chave
    assert partes[1] == "2"
    assert partes[2] == str(tp_amb)
    assert partes[3] == "1"  # cIdToken sem zeros à esquerda
    hash_gerado = partes[4]

    # Validação manual do hash SHA-1 esperado
    payload_to_hash = f"{chave}|2|{tp_amb}|1{csc_token}"
    hash_esperado = hashlib.sha1(payload_to_hash.encode("ascii")).hexdigest().upper()

    assert hash_gerado == hash_esperado
    assert hash_gerado.isupper()


def test_qrcode_generator_injection_into_xml(cert_manager):
    """Valida injeção completa de QR Code v2.0 no nó infNFeSupl de uma NFC-e."""
    emitente_ba = EmitenteInput(
        cnpj="12345678000195",
        razao_social="VAREJO EXPRESS BAHIA",
        ie="123456789",
        crt="1",
        endereco=EnderecoInput(
            logradouro="Rua Chile",
            numero="10",
            bairro="Centro",
            codigo_municipio="2927408",
            nome_municipio="Salvador",
            uf="BA",
            cep="40020000",
        ),
    )

    item = ItemInput(
        numero_item=1,
        codigo="PROD01",
        descricao="Item NFCe",
        ncm="22011000",
        cfop="5102",
        unidade="UN",
        quantidade=Decimal("1.0000"),
        valor_unitario=Decimal("5.00"),
        csosn="102",
    )

    doc_nfce = DocumentoFiscalInput(
        tipo_documento=TipoDocumento.NFCE,
        numero=888,
        serie=1,
        emitente=emitente_ba,
        destinatario=None,
        itens=[item],
        pagamentos=[PagamentoInput(forma=FormaPagamento.DINHEIRO, valor=Decimal("5.00"))],
    )

    doc_proc = TaxEngineSimplesNacional.process(doc_nfce)
    builder = NFeXmlBuilder(doc_proc, c_nf="88776655")
    raw_xml = builder.build()

    signer = XmlSigner(cert_manager)
    signed_xml = signer.sign(raw_xml)

    # Injeta QR Code com CSC de homologação
    xml_com_qr = QRCodeGenerator.inject_qr_code_into_xml(
        xml_input=signed_xml,
        uf_emitente="BA",
        is_production=False,
        c_id_token="000001",
        csc_token="0123456789ABCDEF",
    )

    qr_el = xml_com_qr.find(f".//{{{NFE_NAMESPACE}}}infNFeSupl/{{{NFE_NAMESPACE}}}qrCode")
    assert qr_el is not None
    assert "sefaz.ba.gov.br" in qr_el.text
    assert "?p=" in qr_el.text

    url_el = xml_com_qr.find(f".//{{{NFE_NAMESPACE}}}infNFeSupl/{{{NFE_NAMESPACE}}}urlChave")
    assert url_el is not None
    assert "sefaz.ba.gov.br" in url_el.text
