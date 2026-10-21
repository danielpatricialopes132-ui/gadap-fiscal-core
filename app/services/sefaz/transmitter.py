"""Transmissor SEFAZ: Consulta de Status de Serviço e Envio de Lote Síncrono de NF-e/NFC-e.

Executa:
- Consulta de Status do WebService (consStatServ) com validação de cStat=107.
- Envio de Lote Síncrono (enviNFe com indSinc=1) contra NFeAutorizacao4.
- Anexação de protNFe ao XML assinado, gerando a tag raiz <nfeProc> (documento definitivo).
- Mapeamento e levantamento de SefazRejectionError com sugestão de correção legível para o usuário.
- Mecanismo de resiliência e consulta de chave pré-reemissão em caso de timeout.
"""

from typing import Dict, Optional, Tuple, Union
from dataclasses import dataclass
from lxml import etree

from app.core.config import settings
from app.core.uf_matrix import get_cuf_by_uf
from app.services.sefaz.endpoints import resolve_webservices
from app.services.sefaz.mtls_client import (
    SefazMtlsClient,
    SefazNetworkError,
    NFE_WS_NS,
    NFE_STATUS_WS_NS,
)


NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
NFE_NSMAP = {None: NFE_NAMESPACE}
NFE_CONS_CHAVE_WS_NS = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeConsultaProtocolo4"


# Dicionário de sugestões amigáveis para as rejeições mais frequentes da SEFAZ
SEFAZ_REJEICOES_SUGESTOES: Dict[int, str] = {
    204: "Duplicidade de NF-e: Este número e série de nota já foram autorizados anteriormente na SEFAZ. Consulte o protocolo da chave original ou incremente o número da nota.",
    203: "Emissor não habilitado para emissão da NF-e: Verifique o credenciamento da empresa no portal da SEFAZ da respectiva UF.",
    206: "NF-e já está cancelada na base da SEFAZ.",
    208: "CNPJ do emitente difere do CNPJ do certificado digital A1 utilizado na assinatura.",
    215: "Falha de validação do Schema XML: Uma tag obrigatória está ausente ou com tamanho/formato incorreto.",
    225: "Falha no Schema XML do lote.",
    230: "IE do emitente não cadastrada ou incorreta.",
    232: "IE do emitente não vinculada ao CNPJ na SEFAZ.",
    234: "IE do destinatário não cadastrada ou inválida para a UF.",
    297: "Assinatura difere do calculado: O XML foi alterado após a assinatura digital ou a chave privada é inválida.",
    301: "Uso Denegado: Irregularidade fiscal do emitente junto à SEFAZ.",
    302: "Uso Denegado: Irregularidade fiscal do destinatário junto à SEFAZ.",
    539: "Duplicidade de NF-e com diferença na Chave de Acesso: Já existe nota autorizada com este número/série mas com hash/data diferente.",
    699: "Destaque indevido do ICMS interestadual para a UF de destino (DIFAL): Emitentes do Simples Nacional não devem destacar ICMSUFDest (ADI 5464).",
    703: "NFC-e com data de emissão atrasada.",
    778: "Informado NCM inexistente na tabela da Receita Federal.",
}


class SefazRejectionError(Exception):
    """Exceção levantada quando a SEFAZ rejeita o documento fiscal (cStat >= 200)."""

    def __init__(self, c_stat: int, x_motivo: str, chave_acesso: str = ""):
        self.c_stat = c_stat
        self.x_motivo = x_motivo
        self.chave_acesso = chave_acesso
        self.sugestao = SEFAZ_REJEICOES_SUGESTOES.get(
            c_stat,
            "Verifique os dados cadastrais da empresa e os valores tributários da nota.",
        )

        msg = (
            f"Rejeição SEFAZ [{self.c_stat}]: {self.x_motivo}\n"
            f"Chave de Acesso: {self.chave_acesso or 'N/A'}\n"
            f"Sugestão de Correção: {self.sugestao}"
        )
        super().__init__(msg)


@dataclass
class SefazStatusServicoResult:
    c_stat: int
    x_motivo: str
    tp_amb: int
    dh_retorno: str
    t_med: Optional[int] = None
    is_operacional: bool = False


@dataclass
class SefazAutorizacaoResult:
    c_stat: int
    x_motivo: str
    chave_acesso: str
    n_prot: Optional[str] = None
    dh_recbto: Optional[str] = None
    xml_proc: Optional[str] = None  # XML com a tag raiz <nfeProc> definitiva
    is_autorizado: bool = False


class SefazTransmitter:
    """Orquestrador de envio e recebimento de lotes e consultas com a SEFAZ."""

    def __init__(self, mtls_client: SefazMtlsClient):
        self.client = mtls_client

    def consultar_status_servico(
        self,
        uf: str,
        modelo: str = "55",
        is_production: Optional[bool] = None,
    ) -> SefazStatusServicoResult:
        """Envia consStatServ e valida se cStat=107 (Serviço em Operação)."""
        is_prod = is_production if is_production is not None else settings.is_production
        tp_amb = 1 if is_prod else 2
        c_uf = get_cuf_by_uf(uf)

        # 1. Monta consStatServ
        cons_stat = etree.Element(f"{{{NFE_NAMESPACE}}}consStatServ", versao="4.00", nsmap=NFE_NSMAP)
        etree.SubElement(cons_stat, f"{{{NFE_NAMESPACE}}}tpAmb").text = str(tp_amb)
        etree.SubElement(cons_stat, f"{{{NFE_NAMESPACE}}}cUF").text = c_uf
        etree.SubElement(cons_stat, f"{{{NFE_NAMESPACE}}}xServ").text = "STATUS"

        # 2. Envelopamento SOAP
        envelope_xml = self.client.wrap_soap12_envelope(
            body_element=cons_stat,
            action_namespace=NFE_STATUS_WS_NS,
        )

        # 3. Resolve URL do WebService
        endpoints = resolve_webservices(uf=uf, modelo=modelo, is_production=is_prod)
        url = endpoints.status_servico

        # 4. Transmissão
        res_body = self.client.post_soap(
            url=url,
            envelope_xml=envelope_xml,
            soap_action=f"{NFE_STATUS_WS_NS}/nfeStatusServicoNF",
        )

        # 5. Parse da resposta retConsStatServ
        c_stat_text = res_body.findtext(f".//{{{NFE_NAMESPACE}}}cStat") or res_body.findtext(".//cStat") or "0"
        x_motivo = res_body.findtext(f".//{{{NFE_NAMESPACE}}}xMotivo") or res_body.findtext(".//xMotivo") or ""
        dh_retorno = res_body.findtext(f".//{{{NFE_NAMESPACE}}}dhRecbto") or res_body.findtext(".//dhRecbto") or ""
        t_med_str = res_body.findtext(f".//{{{NFE_NAMESPACE}}}tMed") or res_body.findtext(".//tMed")
        t_med = int(t_med_str) if t_med_str and t_med_str.isdigit() else None

        c_stat = int(c_stat_text)
        is_operacional = (c_stat == 107)

        return SefazStatusServicoResult(
            c_stat=c_stat,
            x_motivo=x_motivo,
            tp_amb=tp_amb,
            dh_retorno=dh_retorno,
            t_med=t_med,
            is_operacional=is_operacional,
        )

    def enviar_lote_sincrono(
        self,
        xml_assinado: Union[bytes, str, etree._Element],
        uf: str,
        modelo: str = "55",
        id_lote: str = "1",
        is_production: Optional[bool] = None,
    ) -> SefazAutorizacaoResult:
        """Envia lote síncrono enviNFe com indSinc=1 contra NFeAutorizacao4.

        Em caso de timeout de rede, aciona automaticamente o mecanismo de resiliência:
        consulta a chave de acesso antes de qualquer reemissão.
        """
        if isinstance(xml_assinado, str):
            nfe_root = etree.fromstring(xml_assinado.encode("utf-8"))
        elif isinstance(xml_assinado, bytes):
            nfe_root = etree.fromstring(xml_assinado)
        else:
            nfe_root = xml_assinado

        # Extrai chave de acesso
        inf_nfe = nfe_root.find(f".//{{{NFE_NAMESPACE}}}infNFe")
        if inf_nfe is None:
            raise ValueError("Tag 'infNFe' não encontrada no XML a ser transmitido.")

        chave_id = inf_nfe.get("Id", "")
        chave_acesso = chave_id.replace("NFe", "")

        is_prod = is_production if is_production is not None else settings.is_production

        # 1. Monta o lote <enviNFe> versao="4.00" com indSinc=1
        envi_nfe = etree.Element(f"{{{NFE_NAMESPACE}}}enviNFe", versao="4.00", nsmap=NFE_NSMAP)
        etree.SubElement(envi_nfe, f"{{{NFE_NAMESPACE}}}idLote").text = str(id_lote)
        etree.SubElement(envi_nfe, f"{{{NFE_NAMESPACE}}}indSinc").text = "1"  # 1 = Processamento síncrono
        envi_nfe.append(nfe_root)

        # 2. Envelopa em SOAP 1.2
        envelope_xml = self.client.wrap_soap12_envelope(
            body_element=envi_nfe,
            action_namespace=NFE_WS_NS,
        )

        endpoints = resolve_webservices(uf=uf, modelo=modelo, is_production=is_prod)
        url = endpoints.autorizacao

        # 3. Transmissão com proteção contra timeout (Resiliência)
        try:
            res_body = self.client.post_soap(
                url=url,
                envelope_xml=envelope_xml,
                soap_action=f"{NFE_WS_NS}/nfeAutorizacaoLote",
            )
        except SefazNetworkError as net_err:
            # MECANISMO DE RESILIÊNCIA: Se ocorreu timeout, verifica se a nota foi autorizada antes de falhar
            consulta_res = self.consultar_chave_acesso(chave_acesso=chave_acesso, uf=uf, is_production=is_prod)
            if consulta_res and consulta_res.is_autorizado:
                return consulta_res
            raise SefazNetworkError(
                f"Falha de rede durante o envio. A nota NÃO foi autorizada na SEFAZ. Erro original: {net_err}"
            ) from net_err

        # 4. Parse do retorno da autorização
        prot_nfe = res_body.find(f".//{{{NFE_NAMESPACE}}}protNFe") or res_body.find(".//protNFe")
        if prot_nfe is None:
            # Pode vir rejeição geral do lote no cStat do retEnviNFe
            c_stat_lote = int(res_body.findtext(f".//{{{NFE_NAMESPACE}}}cStat") or res_body.findtext(".//cStat") or "0")
            x_motivo_lote = res_body.findtext(f".//{{{NFE_NAMESPACE}}}xMotivo") or res_body.findtext(".//xMotivo") or ""
            raise SefazRejectionError(c_stat=c_stat_lote, x_motivo=x_motivo_lote, chave_acesso=chave_acesso)

        # Dados específicos do protocolo
        inf_prot = prot_nfe.find(f"{{{NFE_NAMESPACE}}}infProt") or prot_nfe.find("infProt")
        c_stat = int(inf_prot.findtext(f"{{{NFE_NAMESPACE}}}cStat") or inf_prot.findtext("cStat") or "0")
        x_motivo = inf_prot.findtext(f"{{{NFE_NAMESPACE}}}xMotivo") or inf_prot.findtext("xMotivo") or ""
        n_prot = inf_prot.findtext(f"{{{NFE_NAMESPACE}}}nProt") or inf_prot.findtext("nProt")
        dh_recbto = inf_prot.findtext(f"{{{NFE_NAMESPACE}}}dhRecbto") or inf_prot.findtext("dhRecbto")

        # 5. Tratamento de Sucesso (cStat = 100)
        if c_stat == 100:
            # Monta o XML de distribuição oficial <nfeProc>
            xml_proc = self._build_nfe_proc(nfe_root, prot_nfe)
            return SefazAutorizacaoResult(
                c_stat=c_stat,
                x_motivo=x_motivo,
                chave_acesso=chave_acesso,
                n_prot=n_prot,
                dh_recbto=dh_recbto,
                xml_proc=xml_proc,
                is_autorizado=True,
            )

        # 6. Rejeições (cStat >= 200)
        raise SefazRejectionError(
            c_stat=c_stat,
            x_motivo=x_motivo,
            chave_acesso=chave_acesso,
        )

    def consultar_chave_acesso(
        self,
        chave_acesso: str,
        uf: str,
        is_production: Optional[bool] = None,
    ) -> Optional[SefazAutorizacaoResult]:
        """Consulta o protocolo de uma chave de acesso (NFeConsultaProtocolo4) para resiliência de timeout."""
        is_prod = is_production if is_production is not None else settings.is_production
        tp_amb = 1 if is_prod else 2

        cons_sit = etree.Element(f"{{{NFE_NAMESPACE}}}consSitNFe", versao="4.00", nsmap=NFE_NSMAP)
        etree.SubElement(cons_sit, f"{{{NFE_NAMESPACE}}}tpAmb").text = str(tp_amb)
        etree.SubElement(cons_sit, f"{{{NFE_NAMESPACE}}}xServ").text = "CONSULTAR"
        etree.SubElement(cons_sit, f"{{{NFE_NAMESPACE}}}chNFe").text = chave_acesso

        envelope_xml = self.client.wrap_soap12_envelope(
            body_element=cons_sit,
            action_namespace=NFE_CONS_CHAVE_WS_NS,
        )

        endpoints = resolve_webservices(uf=uf, modelo="55", is_production=is_prod)
        # Normalmente consulta protocolo segue a base do autorizador
        url = endpoints.status_servico.replace("StatusServico", "ConsultaProtocolo").replace("statusservico", "consultaprotocolo")

        try:
            res_body = self.client.post_soap(
                url=url,
                envelope_xml=envelope_xml,
                soap_action=f"{NFE_CONS_CHAVE_WS_NS}/nfeConsultaNF",
            )
            prot = res_body.find(f".//{{{NFE_NAMESPACE}}}protNFe") or res_body.find(".//protNFe")
            if prot is not None:
                inf_prot = prot.find(f"{{{NFE_NAMESPACE}}}infProt") or prot.find("infProt")
                c_stat = int(inf_prot.findtext(f"{{{NFE_NAMESPACE}}}cStat") or inf_prot.findtext("cStat") or "0")
                x_motivo = inf_prot.findtext(f"{{{NFE_NAMESPACE}}}xMotivo") or inf_prot.findtext("xMotivo") or ""
                n_prot = inf_prot.findtext(f"{{{NFE_NAMESPACE}}}nProt") or inf_prot.findtext("nProt")
                dh_recbto = inf_prot.findtext(f"{{{NFE_NAMESPACE}}}dhRecbto") or inf_prot.findtext("dhRecbto")
                return SefazAutorizacaoResult(
                    c_stat=c_stat,
                    x_motivo=x_motivo,
                    chave_acesso=chave_acesso,
                    n_prot=n_prot,
                    dh_recbto=dh_recbto,
                    is_autorizado=(c_stat == 100),
                )
        except Exception:
            return None

        return None

    @staticmethod
    def _build_nfe_proc(nfe_root: etree._Element, prot_nfe: etree._Element) -> str:
        """Constrói o documento legal definitivo <nfeProc versao="4.00"> contendo <NFe> e <protNFe>."""
        nfe_proc = etree.Element(f"{{{NFE_NAMESPACE}}}nfeProc", versao="4.00", nsmap=NFE_NSMAP)
        nfe_proc.append(nfe_root)
        nfe_proc.append(prot_nfe)

        return etree.tostring(
            nfe_proc,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=False,
        ).decode("utf-8")
