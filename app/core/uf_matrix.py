"""Matriz oficial de UFs brasileiras, códigos IBGE (cUF), Autorizadores SEFAZ e Endpoints.

Mapeia as 27 Unidades Federativas do Brasil para seus códigos do IBGE, autorizadores padrão
(Próprio, SVRS ou SVAN), URLs de consulta de status de serviço, autorização de lote e
portais de consulta de QR Code da NFC-e.
"""

from typing import Dict, NamedTuple, Optional


class ServiceEndpoints(NamedTuple):
    status_servico: str
    autorizacao: str
    ret_autorizacao: str


class UFEnvironmentEndpoints(NamedTuple):
    homologacao: ServiceEndpoints
    producao: ServiceEndpoints


class UFInfo(NamedTuple):
    sigla: str
    codigo_ibge: str
    nome: str
    autorizador_nfe: str   # 'PROPRIO', 'SVRS', 'SVAN'
    autorizador_nfce: str  # 'PROPRIO', 'SVRS'
    qr_code_url_homologacao: str
    qr_code_url_producao: str


# ------------------------------------------------------------------------------
# Endpoints Oficiais dos Autorizadores SEFAZ (v4.00)
# ------------------------------------------------------------------------------

# SP - São Paulo
ENDPOINTS_SP_NFE = UFEnvironmentEndpoints(
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

ENDPOINTS_SP_NFCE = UFEnvironmentEndpoints(
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

# BA - Bahia
ENDPOINTS_BA_NFE = UFEnvironmentEndpoints(
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

ENDPOINTS_BA_NFCE = UFEnvironmentEndpoints(
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

# MG - Minas Gerais
ENDPOINTS_MG_NFE = UFEnvironmentEndpoints(
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

ENDPOINTS_MG_NFCE = UFEnvironmentEndpoints(
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

# PR - Paraná
ENDPOINTS_PR_NFE = UFEnvironmentEndpoints(
    homologacao=ServiceEndpoints(
        status_servico="https://homologacao.nfe.fazenda.pr.gov.br/nfe/NFeStatusServico4",
        autorizacao="https://homologacao.nfe.fazenda.pr.gov.br/nfe/NFeAutorizacao4",
        ret_autorizacao="https://homologacao.nfe.fazenda.pr.gov.br/nfe/NFeRetAutorizacao4",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfe.fazenda.pr.gov.br/nfe/NFeStatusServico4",
        autorizacao="https://nfe.fazenda.pr.gov.br/nfe/NFeAutorizacao4",
        ret_autorizacao="https://nfe.fazenda.pr.gov.br/nfe/NFeRetAutorizacao4",
    ),
)

ENDPOINTS_PR_NFCE = UFEnvironmentEndpoints(
    homologacao=ServiceEndpoints(
        status_servico="https://homologacao.nfce.fazenda.pr.gov.br/nfce/NFeStatusServico4",
        autorizacao="https://homologacao.nfce.fazenda.pr.gov.br/nfce/NFeAutorizacao4",
        ret_autorizacao="https://homologacao.nfce.fazenda.pr.gov.br/nfce/NFeRetAutorizacao4",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfce.fazenda.pr.gov.br/nfce/NFeStatusServico4",
        autorizacao="https://nfce.fazenda.pr.gov.br/nfce/NFeAutorizacao4",
        ret_autorizacao="https://nfce.fazenda.pr.gov.br/nfce/NFeRetAutorizacao4",
    ),
)

# RS - Rio Grande do Sul
ENDPOINTS_RS_NFE = UFEnvironmentEndpoints(
    homologacao=ServiceEndpoints(
        status_servico="https://nfe-homologacao.sefaz.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
        autorizacao="https://nfe-homologacao.sefaz.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
        ret_autorizacao="https://nfe-homologacao.sefaz.rs.gov.br/ws/NfeRetAutorizacao/NFeRetAutorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfe.sefaz.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
        autorizacao="https://nfe.sefaz.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
        ret_autorizacao="https://nfe.sefaz.rs.gov.br/ws/NfeRetAutorizacao/NFeRetAutorizacao4.asmx",
    ),
)

# GO - Goiás
ENDPOINTS_GO_NFE = UFEnvironmentEndpoints(
    homologacao=ServiceEndpoints(
        status_servico="https://homolog.sefaz.go.gov.br/nfe/services/NFeStatusServico4",
        autorizacao="https://homolog.sefaz.go.gov.br/nfe/services/NFeAutorizacao4",
        ret_autorizacao="https://homolog.sefaz.go.gov.br/nfe/services/NFeRetAutorizacao4",
    ),
    producao=ServiceEndpoints(
        status_servico="https://nfe.sefaz.go.gov.br/nfe/services/NFeStatusServico4",
        autorizacao="https://nfe.sefaz.go.gov.br/nfe/services/NFeAutorizacao4",
        ret_autorizacao="https://nfe.sefaz.go.gov.br/nfe/services/NFeRetAutorizacao4",
    ),
)

# SVRS - Sefaz Virtual do RS (Atende SC, RJ, ES, CE, PE, AL, PB, RN, PI, TO, SE, PA, AP, AM, RR, AC, RO, DF, etc.)
ENDPOINTS_SVRS_NFE = UFEnvironmentEndpoints(
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

ENDPOINTS_SVRS_NFCE = UFEnvironmentEndpoints(
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

# SVAN - Sefaz Virtual Ambiente Nacional (ex: MA)
ENDPOINTS_SVAN_NFE = UFEnvironmentEndpoints(
    homologacao=ServiceEndpoints(
        status_servico="https://hom.sefazvirtual.fazenda.gov.br/NFeStatusServico4/NFeStatusServico4.asmx",
        autorizacao="https://hom.sefazvirtual.fazenda.gov.br/NFeAutorizacao4/NFeAutorizacao4.asmx",
        ret_autorizacao="https://hom.sefazvirtual.fazenda.gov.br/NFeRetAutorizacao4/NFeRetAutorizacao4.asmx",
    ),
    producao=ServiceEndpoints(
        status_servico="https://www.sefazvirtual.fazenda.gov.br/NFeStatusServico4/NFeStatusServico4.asmx",
        autorizacao="https://www.sefazvirtual.fazenda.gov.br/NFeAutorizacao4/NFeAutorizacao4.asmx",
        ret_autorizacao="https://www.sefazvirtual.fazenda.gov.br/NFeRetAutorizacao4/NFeRetAutorizacao4.asmx",
    ),
)


# ------------------------------------------------------------------------------
# Mapeamento Completo de todas as 27 UFs Brasileiras
# ------------------------------------------------------------------------------
UF_MATRIX: Dict[str, UFInfo] = {
    "RO": UFInfo("RO", "11", "Rondônia", "SVRS", "SVRS", "https://nfce.sefin.ro.gov.br/consultarNFCe.jsp", "https://nfce.sefin.ro.gov.br/consultarNFCe.jsp"),
    "AC": UFInfo("AC", "12", "Acre", "SVRS", "SVRS", "http://hml.sefaznet.ac.gov.br/nfce/qrcode", "http://www.sefaznet.ac.gov.br/nfce/qrcode"),
    "AM": UFInfo("AM", "13", "Amazonas", "PROPRIO", "PROPRIO", "http://homnfce.sefaz.am.gov.br/nfceweb/consultarNFCe.jsp", "http://sistemas.sefaz.am.gov.br/nfceweb/consultarNFCe.jsp"),
    "RR": UFInfo("RR", "14", "Roraima", "SVRS", "SVRS", "http://homologacao.sefaz.rr.gov.br/nfce/qrcode", "https://www.sefaz.rr.gov.br/nfce/qrcode"),
    "PA": UFInfo("PA", "15", "Pará", "SVRS", "SVRS", "https://homnfce.sefa.pa.gov.br/nfce/qrcode", "https://appnfc.sefa.pa.gov.br/portal/qrcode"),
    "AP": UFInfo("AP", "16", "Amapá", "SVRS", "SVRS", "https://www.sefaz.ap.gov.br/nfcehml/qrcode", "https://www.sefaz.ap.gov.br/nfce/qrcode"),
    "TO": UFInfo("TO", "17", "Tocantins", "SVRS", "SVRS", "http://homologacao.sefaz.to.gov.br/nfce/qrcode", "http://www.sefaz.to.gov.br/nfce/qrcode"),
    "MA": UFInfo("MA", "21", "Maranhão", "SVAN", "SVRS", "http://homologacao.sefaz.ma.gov.br/portal/consultarNFCe.jsp", "https://www.sefaz.ma.gov.br/nfce/qrcode"),
    "PI": UFInfo("PI", "22", "Piauí", "SVRS", "SVRS", "http://web.sefaz.pi.gov.br/nfce-homologacao/qrcode", "https://web.sefaz.pi.gov.br/nfce/qrcode"),
    "CE": UFInfo("CE", "23", "Ceará", "SVRS", "SVRS", "http://nfceh.sefaz.ce.gov.br/pages/ShowNFCe.html", "http://nfce.sefaz.ce.gov.br/pages/ShowNFCe.html"),
    "RN": UFInfo("RN", "24", "Rio Grande do Norte", "SVRS", "SVRS", "http://hom.nfce.set.rn.gov.br/consultarNFCe.jsp", "http://nfce.set.rn.gov.br/consultarNFCe.jsp"),
    "PB": UFInfo("PB", "25", "Paraíba", "SVRS", "SVRS", "http://www.sefaz.pb.gov.br/nfcehom", "https://www.sefaz.pb.gov.br/nfce"),
    "PE": UFInfo("PE", "26", "Pernambuco", "SVRS", "SVRS", "http://nfcehomolog.sefaz.pe.gov.br/nfce-web/consultarNFCe", "http://nfce.sefaz.pe.gov.br/nfce-web/consultarNFCe"),
    "AL": UFInfo("AL", "27", "Alagoas", "SVRS", "SVRS", "http://nfce.sefaz.al.gov.br/QRCode/consultarNFCe.jsp", "http://nfce.sefaz.al.gov.br/QRCode/consultarNFCe.jsp"),
    "SE": UFInfo("SE", "28", "Sergipe", "SVRS", "SVRS", "http://homologacao.sefaz.se.gov.br/portal/consultarNFCe.jsp", "http://www.nfce.se.gov.br/portal/consultarNFCe.jsp"),
    "BA": UFInfo("BA", "29", "Bahia", "PROPRIO", "PROPRIO", "http://hnfce.sefaz.ba.gov.br/portal/consultarNFCe.jsp", "http://nfce.sefaz.ba.gov.br/portal/consultarNFCe.jsp"),
    "MG": UFInfo("MG", "31", "Minas Gerais", "PROPRIO", "PROPRIO", "https://hnfce.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml", "https://nfce.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml"),
    "ES": UFInfo("ES", "32", "Espírito Santo", "SVRS", "SVRS", "http://homologacao.sefaz.es.gov.br/ConsultaNFCe/qrcode.aspx", "http://app.sefaz.es.gov.br/ConsultaNFCe/qrcode.aspx"),
    "RJ": UFInfo("RJ", "33", "Rio de Janeiro", "SVRS", "SVRS", "http://www4.fazenda.rj.gov.br/consultaNFCe/QRCode", "http://www4.fazenda.rj.gov.br/consultaNFCe/QRCode"),
    "SP": UFInfo("SP", "35", "São Paulo", "PROPRIO", "PROPRIO", "https://homologacao.nfce.fazenda.sp.gov.br/qrcode", "https://www.nfce.fazenda.sp.gov.br/qrcode"),
    "PR": UFInfo("PR", "41", "Paraná", "PROPRIO", "PROPRIO", "http://www.fazenda.pr.gov.br/nfce/qrcode", "http://www.fazenda.pr.gov.br/nfce/qrcode"),
    "SC": UFInfo("SC", "42", "Santa Catarina", "SVRS", "SVRS", "https://hom.sat.sef.sc.gov.br/nfce/consulta", "https://sat.sef.sc.gov.br/nfce/consulta"),
    "RS": UFInfo("RS", "43", "Rio Grande do Sul", "PROPRIO", "SVRS", "https://nfce-homologacao.sefaz.rs.gov.br/qrcode/qrcode.aspx", "https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx"),
    "MS": UFInfo("MS", "50", "Mato Grosso do Sul", "PROPRIO", "PROPRIO", "http://www.dfe.ms.gov.br/nfce/qrcode", "http://www.dfe.ms.gov.br/nfce/qrcode"),
    "MT": UFInfo("MT", "51", "Mato Grosso", "PROPRIO", "PROPRIO", "https://homologacao.sefaz.mt.gov.br/nfce/consultanfce", "http://www.sefaz.mt.gov.br/nfce/consultanfce"),
    "GO": UFInfo("GO", "52", "Goiás", "PROPRIO", "PROPRIO", "https://homolog.sefaz.go.gov.br/nfce/qrcode", "http://www.sefaz.go.gov.br/nfce/qrcode"),
    "DF": UFInfo("DF", "53", "Distrito Federal", "SVRS", "SVRS", "http://dec.fazenda.df.gov.br/ConsultarNFCe.aspx", "http://dec.fazenda.df.gov.br/ConsultarNFCe.aspx"),
}


def get_uf_info(uf: str) -> UFInfo:
    """Retorna os dados completos da UF fornecida (sigla de 2 caracteres)."""
    uf_upper = uf.strip().upper()
    info = UF_MATRIX.get(uf_upper)
    if not info:
        raise ValueError(f"UF inválida ou não mapeada no Brasil: '{uf}'")
    return info


def get_cuf_by_uf(uf: str) -> str:
    """Retorna o código IBGE de 2 dígitos (cUF) a partir da sigla da UF."""
    return get_uf_info(uf).codigo_ibge


def get_endpoints_for_uf(uf: str, modelo: str = "55") -> UFEnvironmentEndpoints:
    """Retorna os endpoints de Homologação e Produção para a UF e Modelo desejados."""
    info = get_uf_info(uf)
    autorizador = info.autorizador_nfce if modelo == "65" else info.autorizador_nfe

    if info.sigla == "SP":
        return ENDPOINTS_SP_NFCE if modelo == "65" else ENDPOINTS_SP_NFE
    elif info.sigla == "BA":
        return ENDPOINTS_BA_NFCE if modelo == "65" else ENDPOINTS_BA_NFE
    elif info.sigla == "MG":
        return ENDPOINTS_MG_NFCE if modelo == "65" else ENDPOINTS_MG_NFE
    elif info.sigla == "PR":
        return ENDPOINTS_PR_NFCE if modelo == "65" else ENDPOINTS_PR_NFE
    elif info.sigla == "RS":
        return ENDPOINTS_SVRS_NFCE if modelo == "65" else ENDPOINTS_RS_NFE
    elif info.sigla == "GO":
        return ENDPOINTS_SVRS_NFCE if modelo == "65" else ENDPOINTS_GO_NFE
    elif autorizador == "SVAN":
        return ENDPOINTS_SVAN_NFE
    else:
        # Default: SVRS
        return ENDPOINTS_SVRS_NFCE if modelo == "65" else ENDPOINTS_SVRS_NFE


def get_nfce_qr_code_url(uf: str, is_production: bool = False) -> str:
    """Retorna a URL base oficial de consulta de QR Code da NFC-e da respectiva UF."""
    info = get_uf_info(uf)
    return info.qr_code_url_producao if is_production else info.qr_code_url_homologacao
