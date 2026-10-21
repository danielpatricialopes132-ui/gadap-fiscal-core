"""Módulo de configuração global do GADAP Fiscal Core.

Suporta leitura via variáveis de ambiente (.env) usando pydantic-settings.
"""

from enum import Enum
from typing import Literal, Optional
import base64
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DFEEnvironment(str, Enum):
    HOMOLOGACAO = "homologacao"
    PRODUCAO = "producao"


class WebServiceEndpoints(BaseSettings):
    """Mapeamento de endpoints dos WebServices SEFAZ."""

    # SVRS - NF-e (55)
    SVRS_NFE_HOMOLOGACAO_STATUS: str = "https://nfe-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx"
    SVRS_NFE_PRODUCAO_STATUS: str = "https://nfe.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx"
    SVRS_NFE_HOMOLOGACAO_AUTORIZACAO: str = "https://nfe-homologacao.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx"
    SVRS_NFE_PRODUCAO_AUTORIZACAO: str = "https://nfe.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx"

    # SVRS - NFC-e (65)
    SVRS_NFCE_HOMOLOGACAO_STATUS: str = "https://nfce-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx"
    SVRS_NFCE_PRODUCAO_STATUS: str = "https://nfce.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx"
    SVRS_NFCE_HOMOLOGACAO_AUTORIZACAO: str = "https://nfce-homologacao.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx"
    SVRS_NFCE_PRODUCAO_AUTORIZACAO: str = "https://nfce.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx"

    # SP - NF-e (55)
    SP_NFE_HOMOLOGACAO_STATUS: str = "https://homologacao.nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx"
    SP_NFE_PRODUCAO_STATUS: str = "https://nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx"
    SP_NFE_HOMOLOGACAO_AUTORIZACAO: str = "https://homologacao.nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx"
    SP_NFE_PRODUCAO_AUTORIZACAO: str = "https://nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx"

    # SP - NFC-e (65)
    SP_NFCE_HOMOLOGACAO_STATUS: str = "https://homologacao.nfce.fazenda.sp.gov.br/ws/nfestatusservico4.asmx"
    SP_NFCE_PRODUCAO_STATUS: str = "https://nfce.fazenda.sp.gov.br/ws/nfestatusservico4.asmx"
    SP_NFCE_HOMOLOGACAO_AUTORIZACAO: str = "https://homologacao.nfce.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx"
    SP_NFCE_PRODUCAO_AUTORIZACAO: str = "https://nfce.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Identificação da Aplicação
    APP_NAME: str = "GADAP Fiscal Core"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Ambiente DF-e: homologacao ou producao
    DFE_ENVIRONMENT: DFEEnvironment = Field(
        default=DFEEnvironment.HOMOLOGACAO,
        description="Ambiente SEFAZ: 'homologacao' ou 'producao'",
    )

    # Dados do Emitente (Simples Nacional)
    EMITENTE_CNPJ: str = Field(default="", description="CNPJ apenas números")
    EMITENTE_IE: str = Field(default="", description="Inscrição Estadual")
    EMITENTE_UF: str = Field(default="SP", description="Sigla da UF do emitente (ex: SP, RS, etc.)")
    EMITENTE_CRT: Literal["1", "2", "3"] = Field(
        default="1",
        description="Código de Regime Tributário: 1=Simples Nacional, 2=Simples Nacional (excesso), 3=Regime Normal",
    )

    # Certificado Digital A1
    CERTIFICATE_PATH: Optional[str] = Field(
        default=None,
        description="Caminho para arquivo local .pfx / .p12",
    )
    CERTIFICATE_BASE64: Optional[str] = Field(
        default=None,
        description="Conteúdo do certificado .pfx codificado em Base64",
    )
    CERTIFICATE_PASSWORD: str = Field(
        default="",
        description="Senha de acesso à chave privada do certificado A1",
    )

    # Credenciais NFC-e (CSC - Código de Segurança do Contribuinte)
    CSC_HOMOLOGACAO_ID: str = Field(default="000001", description="IdToken / Identificador do CSC de homologação")
    CSC_HOMOLOGACAO_TOKEN: str = Field(default="", description="Código alfanumérico do CSC de homologação")
    CSC_PRODUCAO_ID: str = Field(default="", description="IdToken / Identificador do CSC de produção")
    CSC_PRODUCAO_TOKEN: str = Field(default="", description="Código alfanumérico do CSC de produção")

    # Supabase (Banco de Dados & Storage)
    SUPABASE_URL: Optional[str] = Field(default=None, description="URL do projeto Supabase")
    SUPABASE_KEY: Optional[str] = Field(default=None, description="Chave de API / Service Key Supabase")
    DATABASE_URL: Optional[str] = Field(default=None, description="String de conexão PostgreSQL do Supabase")

    # Endpoints de WebServices
    webservices: WebServiceEndpoints = Field(default_factory=WebServiceEndpoints)

    @property
    def tp_amb(self) -> int:
        """Retorna o código SEFAZ de tipo de ambiente: 1 para Produção, 2 para Homologação."""
        return 1 if self.DFE_ENVIRONMENT == DFEEnvironment.PRODUCAO else 2

    @property
    def is_production(self) -> bool:
        """Indica se está operando em ambiente de produção."""
        return self.DFE_ENVIRONMENT == DFEEnvironment.PRODUCAO

    @property
    def active_csc_id(self) -> str:
        """Obtém o ID do CSC correspondente ao ambiente ativo."""
        return self.CSC_PRODUCAO_ID if self.is_production else self.CSC_HOMOLOGACAO_ID

    @property
    def active_csc_token(self) -> str:
        """Obtém o token do CSC correspondente ao ambiente ativo."""
        return self.CSC_PRODUCAO_TOKEN if self.is_production else self.CSC_HOMOLOGACAO_TOKEN

    def get_certificate_bytes(self) -> Optional[bytes]:
        """Obtém os bytes do certificado A1 a partir de Base64 ou de arquivo em disco."""
        if self.CERTIFICATE_BASE64:
            return base64.b64decode(self.CERTIFICATE_BASE64)
        if self.CERTIFICATE_PATH:
            with open(self.CERTIFICATE_PATH, "rb") as f:
                return f.read()
        return None

    def get_status_service_url(self, uf: Optional[str] = None, modelo: Literal["55", "65"] = "55") -> str:
        """Retorna a URL do serviço de Status de Serviço conforme UF, Modelo e Ambiente."""
        from app.services.sefaz.endpoints import resolve_webservices
        target_uf = (uf or self.EMITENTE_UF).upper()
        endpoints = resolve_webservices(uf=target_uf, modelo=modelo, is_production=self.is_production)
        return endpoints.status_servico

    def get_autorizacao_service_url(self, uf: Optional[str] = None, modelo: Literal["55", "65"] = "55") -> str:
        """Retorna a URL do serviço de Autorização conforme UF, Modelo e Ambiente."""
        from app.services.sefaz.endpoints import resolve_webservices
        target_uf = (uf or self.EMITENTE_UF).upper()
        endpoints = resolve_webservices(uf=target_uf, modelo=modelo, is_production=self.is_production)
        return endpoints.autorizacao

    def get_ret_autorizacao_service_url(self, uf: Optional[str] = None, modelo: Literal["55", "65"] = "55") -> str:
        """Retorna a URL do serviço de Consulta do Recibo de Lote (RetAutorizacao)."""
        from app.services.sefaz.endpoints import resolve_webservices
        target_uf = (uf or self.EMITENTE_UF).upper()
        endpoints = resolve_webservices(uf=target_uf, modelo=modelo, is_production=self.is_production)
        return endpoints.ret_autorizacao


settings = Settings()
