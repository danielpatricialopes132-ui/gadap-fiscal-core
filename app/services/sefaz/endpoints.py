"""Mapeamento Multi-UF dos WebServices SEFAZ (SP, BA, RJ, MG e SVRS).

Contempla os serviços de StatusServico, Autorizacao e RetAutorizacao
para NF-e (modelo 55) e NFC-e (modelo 65) nos ambientes de Homologação e Produção.
"""

from typing import Dict, Literal, NamedTuple


class ServiceEndpoints(NamedTuple):
    status_servico: str
    autorizacao: str
    ret_autorizacao: str


class UFWebServices(NamedTuple):
    homologacao: ServiceEndpoints
    producao: ServiceEndpoints


# Mapeamento detalhado dos WebServices por Autorizador/UF
# SP - São Paulo (Servidor próprio)
SP_NFE = UFWebServices(
    homologacao=ServiceEndpoints(
        status_servico="https://homologacao.nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
        autorizacao="https://homologacao.nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx",
        ret_autorizacao="https://homologacao.nfe.fazenda.sp.gov.br/ws/nferetautorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
        autorizacao="https://nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx",
        ret_autorizacao="https://nfe.fazenda.sp.gov.br/ws/nferetautorizacao4.asmx",
    ),
)

SP_NFCE = UFWebServices(
    homologacao=ServiceEndpoints(
        status_servico="https://homologacao.nfce.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
        autorizacao="https://homologacao.nfce.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx",
        ret_autorizacao="https://homologacao.nfce.fazenda.sp.gov.br/ws/nferetautorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfce.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
        autorizacao="https://nfce.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx",
        ret_autorizacao="https://nfce.fazenda.sp.gov.br/ws/nferetautorizacao4.asmx",
    ),
)

# BA - Bahia (Servidor próprio)
BA_NFE = UFWebServices(
    homologacao=ServiceEndpoints(
        status_servico="https://hnfe.sefaz.ba.gov.br/ws/NfeStatusServico4.asmx",
        autorizacao="https://hnfe.sefaz.ba.gov.br/ws/NFeAutorizacao4.asmx",
        ret_autorizacao="https://hnfe.sefaz.ba.gov.br/ws/NFeRetAutorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfe.sefaz.ba.gov.br/ws/NfeStatusServico4.asmx",
        autorizacao="https://nfe.sefaz.ba.gov.br/ws/NFeAutorizacao4.asmx",
        ret_autorizacao="https://nfe.sefaz.ba.gov.br/ws/NFeRetAutorizacao4.asmx",
    ),
)

BA_NFCE = UFWebServices(
    homologacao=ServiceEndpoints(
        status_servico="https://hnfce.sefaz.ba.gov.br/ws/NfeStatusServico4.asmx",
        autorizacao="https://hnfce.sefaz.ba.gov.br/ws/NfeAutorizacao4.asmx",
        ret_autorizacao="https://hnfce.sefaz.ba.gov.br/ws/NfeRetAutorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfce.sefaz.ba.gov.br/ws/NfeStatusServico4.asmx",
        autorizacao="https://nfce.sefaz.ba.gov.br/ws/NfeAutorizacao4.asmx",
        ret_autorizacao="https://nfce.sefaz.ba.gov.br/ws/NfeRetAutorizacao4.asmx",
    ),
)

# MG - Minas Gerais (Servidor próprio)
MG_NFE = UFWebServices(
    homologacao=ServiceEndpoints(
        status_servico="https://hnfe.fazenda.mg.gov.br/nfe2/services/NFeStatusServico4",
        autorizacao="https://hnfe.fazenda.mg.gov.br/nfe2/services/NFeAutorizacao4",
        ret_autorizacao="https://hnfe.fazenda.mg.gov.br/nfe2/services/NFeRetAutorizacao4",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfe.fazenda.mg.gov.br/nfe2/services/NFeStatusServico4",
        autorizacao="https://nfe.fazenda.mg.gov.br/nfe2/services/NFeAutorizacao4",
        ret_autorizacao="https://nfe.fazenda.mg.gov.br/nfe2/services/NFeRetAutorizacao4",
    ),
)

MG_NFCE = UFWebServices(
    homologacao=ServiceEndpoints(
        status_servico="https://hnfce.fazenda.mg.gov.br/nfce/services/NFeStatusServico4",
        autorizacao="https://hnfce.fazenda.mg.gov.br/nfce/services/NFeAutorizacao4",
        ret_autorizacao="https://hnfce.fazenda.mg.gov.br/nfce/services/NFeRetAutorizacao4",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfce.fazenda.mg.gov.br/nfce/services/NFeStatusServico4",
        autorizacao="https://nfce.fazenda.mg.gov.br/nfce/services/NFeAutorizacao4",
        ret_autorizacao="https://nfce.fazenda.mg.gov.br/nfce/services/NFeRetAutorizacao4",
    ),
)

# SVRS - Sefaz Virtual do Rio Grande do Sul (Atende RJ e diversos outros estados)
SVRS_NFE = UFWebServices(
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

SVRS_NFCE = UFWebServices(
    homologacao=ServiceEndpoints(
        status_servico="https://nfce-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
        autorizacao="https://nfce-homologacao.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
        ret_autorizacao="https://nfce-homologacao.svrs.rs.gov.br/ws/NfeRetAutorizacao/NFeRetAutorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfce.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
        autorizacao="https://nfce.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
        ret_autorizacao="https://nfce.svrs.rs.gov.br/ws/NfeRetAutorizacao/NFeRetAutorizacao4.asmx",
    ),
)

# Tabela de roteamento por UF:
# RJ usa SVRS tanto para NF-e quanto para NFC-e.
# SP, BA e MG utilizam seus autorizadores próprios.
# Demais UFs caem por padrão na SVRS.
UF_REGISTRY: Dict[str, Dict[str, UFWebServices]] = {
    "SP": {"55": SP_NFE, "65": SP_NFCE},
    "BA": {"55": BA_NFE, "65": BA_NFCE},
    "MG": {"55": MG_NFE, "65": MG_NFCE},
    "RJ": {"55": SVRS_NFE, "65": SVRS_NFCE},
    "SVRS": {"55": SVRS_NFE, "65": SVRS_NFCE},
}


def resolve_webservices(
    uf: str,
    modelo: Literal["55", "65"] = "55",
    is_production: bool = False,
) -> ServiceEndpoints:
    """Resolve os endpoints dos WebServices SEFAZ da UF especificada.

    Args:
        uf: Sigla da UF (ex: 'SP', 'BA', 'RJ', 'MG', 'RS') ou 'SVRS'.
        modelo: '55' (NF-e) ou '65' (NFC-e).
        is_production: True para Produção, False para Homologação.

    Returns:
        ServiceEndpoints: Instância com status_servico, autorizacao e ret_autorizacao.
    """
    uf_clean = uf.strip().upper()
    uf_config = UF_REGISTRY.get(uf_clean, UF_REGISTRY["SVRS"])
    model_config = uf_config.get(modelo, uf_config["55"])

    return model_config.producao if is_production else model_config.homologacao
