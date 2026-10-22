"""Roteador de Contingência Autônoma e Resiliência da SEFAZ.

Comutação Inteligente:
1. Detecção de Indisponibilidade:
   - Monitoramento de falhas consecutivas (threshold: 3 falhas ou timeouts > 15s).
   - Classificação de oscilação do servidor estadual.
2. Comutação de NF-e (Modelo 55):
   - Redirecionamento automático para SVC (Sefaz Virtual de Contingência):
     * SVC-AN: AC, AL, AP, DF, ES, MG, PB, RJ, RN, RO, RR, RS, SC, SE, SP, TO.
     * SVC-RS: AM, BA, CE, GO, MA, MS, MT, PA, PE, PI, PR.
3. Comutação de NFC-e (Modelo 65):
   - Ativação de Emissão em Contingência Offline (tpEmis = 9) com geração de DANFE
     simplificado em bobina térmica e gravação para transmissão síncrona posterior.
"""

from typing import Dict, Any, Optional, Tuple
from enum import Enum
from datetime import datetime, timezone
import logging

from app.core.uf_matrix import get_uf_info, ServiceEndpoints, UFEnvironmentEndpoints
from app.core.config import settings

logger = logging.getLogger("gadap.sefaz.contingency")


class TipoContingencia(str, Enum):
    NORMAL = "1"
    SVC_AN = "6"
    SVC_RS = "7"
    OFFLINE_NFCE = "9"


# Endpoints Oficiais dos Servidores Virtuais de Contingência (SVC v4.00)
SVC_AN_ENDPOINTS = UFEnvironmentEndpoints(
    homologacao=ServiceEndpoints(
        status_servico="https://hom.svc.fazenda.gov.br/NFeStatusServico4/NFeStatusServico4.asmx",
        autorizacao="https://hom.svc.fazenda.gov.br/NFeAutorizacao4/NFeAutorizacao4.asmx",
        ret_autorizacao="https://hom.svc.fazenda.gov.br/NFeRetAutorizacao4/NFeRetAutorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://www.svc.fazenda.gov.br/NFeStatusServico4/NFeStatusServico4.asmx",
        autorizacao="https://www.svc.fazenda.gov.br/NFeAutorizacao4/NFeAutorizacao4.asmx",
        ret_autorizacao="https://www.svc.fazenda.gov.br/NFeRetAutorizacao4/NFeRetAutorizacao4.asmx",
    ),
)

SVC_RS_ENDPOINTS = UFEnvironmentEndpoints(
    homologacao=ServiceEndpoints(
        status_servico="https://nfe-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
        autorizacao="https://nfe-homologacao.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
        ret_autorizacao="https://nfe-homologacao.svrs.rs.gov.br/ws/NfeRetAutorizacao/NFeRetAutorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfe.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
        autorizacao="https://nfe.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
        ret_autorizacao="https://nfe.svrs.rs.gov.br/ws/NfeRetAutorizacao/NFeRetAutorizacao4.asmx",
    ),
)

# Mapeamento Oficial das UFs atendidas por cada SVC para NF-e (Modelo 55)
# UFs atendidas pela SVC-AN (Ambiente Nacional):
UFS_SVC_AN = {
    "AC", "AL", "AP", "DF", "ES", "MG", "PB", "RJ",
    "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}

# UFs atendidas pela SVC-RS (Rio Grande do Sul):
UFS_SVC_RS = {
    "AM", "BA", "CE", "GO", "MA", "MS", "MT", "PA", "PE", "PI", "PR",
}


class SefazContingencyRouter:
    """Gerenciador de integridade e roteamento autônomo de contingência SEFAZ."""

    # Estado em memória de falhas consecutivas por UF e Modelo
    _falhas_consecutivas: Dict[str, int] = {}
    _contingencia_ativa: Dict[str, TipoContingencia] = {}

    @classmethod
    def registrar_falha(cls, uf: str, modelo: str = "55", motivo: str = "Timeout / Conexão") -> TipoContingencia:
        """Registra uma falha de conexão e avalia se comuta para contingência."""
        key = f"{uf.upper()}_{modelo}"
        cls._falhas_consecutivas[key] = cls._falhas_consecutivas.get(key, 0) + 1
        falhas = cls._falhas_consecutivas[key]

        logger.warning(f"SEFAZ-{uf} [Modelo {modelo}] registrou falha #{falhas}: {motivo}")

        # Limiar de 3 falhas consecutivas para comutação autônoma
        if falhas >= 3:
            return cls.ativar_contingencia(uf=uf, modelo=modelo, motivo=motivo)

        return cls._contingencia_ativa.get(key, TipoContingencia.NORMAL)

    @classmethod
    def registrar_sucesso(cls, uf: str, modelo: str = "55") -> None:
        """Restaura o estado normal da SEFAZ após resposta bem-sucedida."""
        key = f"{uf.upper()}_{modelo}"
        if cls._falhas_consecutivas.get(key, 0) > 0:
            cls._falhas_consecutivas[key] = 0
            if key in cls._contingencia_ativa and cls._contingencia_ativa[key] != TipoContingencia.NORMAL:
                logger.info(f"SEFAZ-{uf} restabeleceu operação normal. Encerrando contingência.")
                cls._contingencia_ativa[key] = TipoContingencia.NORMAL

    @classmethod
    def ativar_contingencia(cls, uf: str, modelo: str = "55", motivo: str = "Oscilação") -> TipoContingencia:
        """Determina o tipo correto de contingência para a UF e Modelo."""
        key = f"{uf.upper()}_{modelo}"
        uf_upper = uf.upper()

        if modelo == "65":
            # Para NFC-e, a contingência legal padrão é a Emissão Offline (tpEmis = 9)
            contingencia = TipoContingencia.OFFLINE_NFCE
            logger.critical(f"⚠️ COMUTAÇÃO AUTÔNOMA: SEFAZ-{uf} (NFC-e) -> MODO OFFLINE (tpEmis=9). Motivo: {motivo}")
        else:
            # Para NF-e (modelo 55), comuta para SVC-AN ou SVC-RS
            if uf_upper in UFS_SVC_AN:
                contingencia = TipoContingencia.SVC_AN
                logger.critical(f"⚠️ COMUTAÇÃO AUTÔNOMA: SEFAZ-{uf} (NF-e) -> SVC-AN (tpEmis=6). Motivo: {motivo}")
            else:
                contingencia = TipoContingencia.SVC_RS
                logger.critical(f"⚠️ COMUTAÇÃO AUTÔNOMA: SEFAZ-{uf} (NF-e) -> SVC-RS (tpEmis=7). Motivo: {motivo}")

        cls._contingencia_ativa[key] = contingencia
        return contingencia

    @classmethod
    def obter_status_contingencia(cls, uf: str, modelo: str = "55") -> TipoContingencia:
        """Retorna o tipo de emissão atual (NORMAL, SVC_AN, SVC_RS ou OFFLINE_NFCE)."""
        key = f"{uf.upper()}_{modelo}"
        return cls._contingencia_ativa.get(key, TipoContingencia.NORMAL)

    @classmethod
    def resolver_endpoints(
        cls,
        uf: str,
        modelo: str = "55",
        is_production: Optional[bool] = None,
    ) -> Tuple[ServiceEndpoints, TipoContingencia]:
        """Resolve a URL de autorização correta considerando o estado de contingência."""
        from app.core.uf_matrix import get_endpoints_for_uf

        prod = settings.is_production if is_production is None else is_production
        modo = cls.obter_status_contingencia(uf, modelo)

        if modo == TipoContingencia.SVC_AN:
            ep = SVC_AN_ENDPOINTS.producao if prod else SVC_AN_ENDPOINTS.homologacao
            return ep, modo
        elif modo == TipoContingencia.SVC_RS:
            ep = SVC_RS_ENDPOINTS.producao if prod else SVC_RS_ENDPOINTS.homologacao
            return ep, modo
        else:
            # Normal ou Offline
            endpoints_uf = get_endpoints_for_uf(uf, modelo)
            ep = endpoints_uf.producao if prod else endpoints_uf.homologacao
            return ep, modo
