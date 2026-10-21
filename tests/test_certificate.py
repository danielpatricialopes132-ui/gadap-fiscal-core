"""Testes unitários para o gerenciador de Certificado Digital A1."""

from datetime import datetime, timedelta, timezone
import base64
import pytest

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption, NoEncryption

from app.core.security.certificate import A1CertificateManager, CertificateError
from app.core.config import Settings, DFEEnvironment


def generate_self_signed_pfx(
    common_name: str = "EMPRESA TESTE LTDA:12345678000199",
    password: str = "senha123",
    days_valid: int = 365,
    expired: bool = False,
) -> bytes:
    """Gera um arquivo PFX/P12 em memória para testes unitários."""
    # Gera chave privada RSA
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    now = datetime.now(timezone.utc)
    if expired:
        not_valid_before = now - timedelta(days=days_valid + 10)
        not_valid_after = now - timedelta(days=10)
    else:
        not_valid_before = now - timedelta(days=1)
        not_valid_after = now + timedelta(days=days_valid)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "SP"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil Teste"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )

    encryption = (
        BestAvailableEncryption(password.encode("utf-8"))
        if password
        else NoEncryption()
    )

    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"certificado_teste",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=encryption,
    )

    return pfx_bytes


def test_certificate_loading_and_properties():
    password = "segredo_fiscal"
    cn = "TESTE SOFTWARE FISCAL ME:00000000000191"
    pfx_data = generate_self_signed_pfx(common_name=cn, password=password, days_valid=30)

    mgr = A1CertificateManager(pfx_data=pfx_data, password=password)

    assert mgr.get_subject_name() == cn
    assert not mgr.is_expired()
    assert mgr.not_valid_after > datetime.now(timezone.utc)
    assert mgr.not_valid_before < datetime.now(timezone.utc)
    assert len(mgr.get_serial_number()) > 0


def test_certificate_pem_export():
    password = "123"
    pfx_data = generate_self_signed_pfx(password=password)
    mgr = A1CertificateManager(pfx_data=pfx_data, password=password)

    cert_pem, key_pem = mgr.export_pem_tuple()

    assert b"-----BEGIN CERTIFICATE-----" in cert_pem
    assert b"-----END CERTIFICATE-----" in cert_pem
    assert b"-----BEGIN RSA PRIVATE KEY-----" in key_pem
    assert b"-----END RSA PRIVATE KEY-----" in key_pem


def test_certificate_expired_detection():
    password = "123"
    pfx_data = generate_self_signed_pfx(password=password, expired=True)
    mgr = A1CertificateManager(pfx_data=pfx_data, password=password)

    assert mgr.is_expired() is True


def test_certificate_from_base64():
    password = "base64_test_pass"
    pfx_data = generate_self_signed_pfx(password=password)
    b64_str = base64.b64encode(pfx_data).decode("ascii")

    mgr = A1CertificateManager.from_base64(b64_str, password)
    assert not mgr.is_expired()
    assert b"BEGIN CERTIFICATE" in mgr.export_certificate_pem()


def test_certificate_wrong_password():
    pfx_data = generate_self_signed_pfx(password="senha_certa")
    with pytest.raises(CertificateError):
        A1CertificateManager(pfx_data=pfx_data, password="senha_errada")


def test_config_dfe_environment_helpers():
    # Teste em Homologação
    cfg_hom = Settings(DFE_ENVIRONMENT=DFEEnvironment.HOMOLOGACAO, EMITENTE_UF="SP")
    assert cfg_hom.tp_amb == 2
    assert not cfg_hom.is_production
    assert "homologacao" in cfg_hom.get_status_service_url(modelo="55")
    assert "homologacao" in cfg_hom.get_autorizacao_service_url(modelo="65")

    # Teste em Produção
    cfg_prod = Settings(DFE_ENVIRONMENT=DFEEnvironment.PRODUCAO, EMITENTE_UF="SP")
    assert cfg_prod.tp_amb == 1
    assert cfg_prod.is_production
    assert "homologacao" not in cfg_prod.get_status_service_url(modelo="55")
    assert "homologacao" not in cfg_prod.get_autorizacao_service_url(modelo="65")

    # Teste SVRS
    cfg_rs = Settings(DFE_ENVIRONMENT=DFEEnvironment.HOMOLOGACAO, EMITENTE_UF="RS")
    assert "svrs" in cfg_rs.get_status_service_url(modelo="55")
