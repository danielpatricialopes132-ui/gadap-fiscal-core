"""Módulo de gerenciamento de Certificado Digital A1 (.pfx / .p12).

Realiza extração e manipulação estritamente em memória da chave privada RSA,
certificado X.509 e cadeias intermediárias para autenticação TLS e assinatura XML.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
import base64

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12


class CertificateError(Exception):
    """Exceção base para erros relacionados ao manuseio do certificado."""
    pass


class CertificateExpiredError(CertificateError):
    """Exceção levantada quando o certificado digital está fora da validade."""
    pass


class A1CertificateManager:
    """Gerenciador de Certificado Digital ICP-Brasil padrão A1."""

    def __init__(self, pfx_data: bytes, password: str):
        """Inicializa o gerenciador a partir dos bytes do arquivo PFX e sua senha.

        Args:
            pfx_data: Binário do arquivo .pfx / .p12
            password: Senha em texto claro da chave privada
        """
        if not pfx_data:
            raise CertificateError("Conteúdo do arquivo PFX não pode ser vazio.")

        self._password_bytes = password.encode("utf-8") if password else None
        self._private_key: Optional[rsa.RSAPrivateKey] = None
        self._certificate: Optional[x509.Certificate] = None
        self._additional_certificates: List[x509.Certificate] = []

        self._load_pkcs12(pfx_data)

    @classmethod
    def from_file(cls, filepath: str, password: str) -> "A1CertificateManager":
        """Carrega o certificado a partir de um arquivo no disco."""
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            return cls(content, password)
        except FileNotFoundError:
            raise CertificateError(f"Arquivo de certificado não encontrado: {filepath}")
        except Exception as e:
            raise CertificateError(f"Falha ao ler arquivo de certificado: {e}")

    @classmethod
    def from_base64(cls, base64_str: str, password: str) -> "A1CertificateManager":
        """Carrega o certificado a partir de uma string Base64."""
        try:
            raw_bytes = base64.b64decode(base64_str)
            return cls(raw_bytes, password)
        except Exception as e:
            raise CertificateError(f"Falha ao decodificar certificado em Base64: {e}")

    def _load_pkcs12(self, pfx_data: bytes) -> None:
        """Extrai chave privada, certificado e cadeias intermediárias em memória."""
        try:
            private_key, certificate, additional_certificates = (
                pkcs12.load_key_and_certificates(
                    pfx_data,
                    self._password_bytes,
                )
            )
        except Exception as e:
            raise CertificateError(f"Falha ao abrir PKCS#12 (senha incorreta ou formato inválido): {e}")

        if certificate is None:
            raise CertificateError("Nenhum certificado X.509 encontrado no container PFX.")

        if private_key is None:
            raise CertificateError("Nenhuma chave privada encontrada no container PFX.")

        self._private_key = private_key
        self._certificate = certificate
        self._additional_certificates = additional_certificates or []

    @property
    def certificate(self) -> x509.Certificate:
        """Retorna o objeto X.509 Certificate da cryptography."""
        if not self._certificate:
            raise CertificateError("Certificado não carregado.")
        return self._certificate

    @property
    def private_key(self) -> rsa.RSAPrivateKey:
        """Retorna o objeto RSAPrivateKey da cryptography."""
        if not self._private_key:
            raise CertificateError("Chave privada não carregada.")
        return self._private_key

    @property
    def additional_certificates(self) -> List[x509.Certificate]:
        """Retorna a lista de certificados adicionais/cadeias intermediárias."""
        return self._additional_certificates

    @property
    def not_valid_before(self) -> datetime:
        """Data/hora UTC inicial de validade do certificado."""
        # Suporte retrocompatível com versões cryptography que migraram para _utc
        cert = self.certificate
        if hasattr(cert, "not_valid_before_utc"):
            return cert.not_valid_before_utc
        return cert.not_valid_before.replace(tzinfo=timezone.utc)

    @property
    def not_valid_after(self) -> datetime:
        """Data/hora UTC final de validade (expiração) do certificado."""
        cert = self.certificate
        if hasattr(cert, "not_valid_after_utc"):
            return cert.not_valid_after_utc
        return cert.not_valid_after.replace(tzinfo=timezone.utc)

    def is_expired(self, reference_time: Optional[datetime] = None) -> bool:
        """Verifica se o certificado está expirado em relação ao horário de referência.

        Args:
            reference_time: Datetime com fuso horário (default: datetime.now(timezone.utc))

        Returns:
            bool: True se estiver fora da validade (expirado ou antes do início).
        """
        now = reference_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        return now > self.not_valid_after or now < self.not_valid_before

    def get_subject_name(self) -> str:
        """Retorna o Common Name (CN) do titular do certificado."""
        cns = self.certificate.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
        if cns:
            return cns[0].value
        return self.certificate.subject.rfc4514_string()

    def get_serial_number(self) -> str:
        """Retorna o número de série em formato hexadecimal."""
        return format(self.certificate.serial_number, "X")

    def export_private_key_pem(self, password: Optional[str] = None) -> bytes:
        """Exporta a chave privada em formato PEM (em memória).

        Args:
            password: Se fornecido, criptografa a PEM com a senha dada; caso contrário, exporta sem criptografia.
        """
        encryption = (
            serialization.BestAvailableEncryption(password.encode("utf-8"))
            if password
            else serialization.NoEncryption()
        )
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption,
        )

    def export_certificate_pem(self) -> bytes:
        """Exporta o certificado público X.509 em formato PEM (em memória)."""
        return self.certificate.public_bytes(encoding=serialization.Encoding.PEM)

    def export_chain_pem(self) -> bytes:
        """Exporta a cadeia completa (certificado titular + certificados intermediários) em PEM."""
        pem_parts = [self.export_certificate_pem()]
        for cert in self._additional_certificates:
            pem_parts.append(cert.public_bytes(encoding=serialization.Encoding.PEM))
        return b"\n".join(pem_parts)

    def export_pem_tuple(self) -> Tuple[bytes, bytes]:
        """Exporta a tupla (cert_pem, key_pem) em memória para uso em mTLS / requests.

        Returns:
            Tuple[bytes, bytes]: (certificado_pem, chave_privada_pem)
        """
        return self.export_certificate_pem(), self.export_private_key_pem()
