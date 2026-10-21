"""Módulo de Eventos SEFAZ: Cancelamento de NF-e/NFC-e e Carta de Correção Eletrônica (CC-e).

Tipos de Eventos Oficiais:
- Cancelamento por homologação: tpEvento = 110111
- Carta de Correção Eletrônica: tpEvento = 110110
Serviço SEFAZ: NFeRecepcaoEvento4
"""

from typing import Optional, Union
from datetime import datetime, timezone
from dataclasses import dataclass
from lxml import etree

from app.core.config import settings
from app.core.uf_matrix import get_cuf_by_uf
from app.services.sefaz.endpoints import resolve_webservices
from app.services.sefaz.xml_signer import XmlSigner
from app.services.sefaz.mtls_client import SefazMtlsClient
from app.services.sefaz.transmitter import SefazRejectionError


NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
NFE_NSMAP = {None: NFE_NAMESPACE}
NFE_EVENTO_WS_NS = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4"

EVENTO_CANCELAMENTO = "110111"
EVENTO_CCE = "110110"


@dataclass
class SefazEventoResult:
    c_stat: int
    x_motivo: str
    tp_evento: str
    chave_acesso: str
    n_seq_evento: int
    n_prot: Optional[str] = None
    dh_reg_evento: Optional[str] = None
    xml_proc_evento: Optional[str] = None
    is_homologado: bool = False


class SefazEventManager:
    """Gerencia a criação, assinatura e transmissão de eventos fiscais (Cancelamento e CC-e)."""

    def __init__(self, mtls_client: SefazMtlsClient, signer: XmlSigner):
        self.client = mtls_client
        self.signer = signer

    def cancelar_documento(
        self,
        chave_acesso: str,
        n_protocolo_autorizacao: str,
        justificativa: str,
        cnpj_emitente: str,
        uf: str,
        modelo: str = "55",
        n_seq_evento: int = 1,
        is_production: Optional[bool] = None,
    ) -> SefazEventoResult:
        """Cancela uma NF-e ou NFC-e previamente autorizada.

        A justificativa deve ter entre 15 e 255 caracteres.
        """
        just_clean = justificativa.strip()
        if len(just_clean) < 15:
            raise ValueError("Justificativa de cancelamento deve ter no mínimo 15 caracteres.")
        if len(just_clean) > 255:
            just_clean = just_clean[:255]

        return self._emitir_evento(
            chave_acesso=chave_acesso,
            tp_evento=EVENTO_CANCELAMENTO,
            desc_evento="Cancelamento",
            det_evento_xml=f"<nProt>{n_protocolo_autorizacao}</nProt><xJust>{just_clean}</xJust>",
            cnpj_autor=cnpj_emitente,
            uf=uf,
            modelo=modelo,
            n_seq_evento=n_seq_evento,
            is_production=is_production,
        )

    def carta_correcao(
        self,
        chave_acesso: str,
        texto_correcao: str,
        cnpj_emitente: str,
        uf: str,
        modelo: str = "55",
        n_seq_evento: int = 1,
        is_production: Optional[bool] = None,
    ) -> SefazEventoResult:
        """Emite uma Carta de Correção Eletrônica (CC-e) para retificar dados não cadastrais/tributários essenciais.

        O texto da correção deve ter entre 15 e 1000 caracteres.
        """
        texto_clean = texto_correcao.strip()
        if len(texto_clean) < 15:
            raise ValueError("Texto da Carta de Correção deve ter no mínimo 15 caracteres.")
        if len(texto_clean) > 1000:
            texto_clean = texto_clean[:1000]

        cond_uso = (
            "A Carta de Correcao e disciplinada pelo paragrafo 1o-A do art. 7o do Convenio S/N, "
            "de 15 de dezembro de 1970 e pode ser utilizada para regularizacao de erro ocorrido na "
            "emissao de documento fiscal, desde que o erro nao esteja relacionado com: "
            "I - as variaveis que determinam o valor do imposto tais como: base de calculo, aliquota, "
            "diferenca de preco, quantidade, valor da operacao ou da prestacao; "
            "II - a correcao de dados cadastrais que implique mudanca do remetente ou do destinatario; "
            "III - a data de emissao ou de saida."
        )

        det_xml = f"<xCorrecao>{texto_clean}</xCorrecao><xCondUso>{cond_uso}</xCondUso>"

        return self._emitir_evento(
            chave_acesso=chave_acesso,
            tp_evento=EVENTO_CCE,
            desc_evento="Carta de Correcao",
            det_evento_xml=det_xml,
            cnpj_autor=cnpj_emitente,
            uf=uf,
            modelo=modelo,
            n_seq_evento=n_seq_evento,
            is_production=is_production,
        )

    def _emitir_evento(
        self,
        chave_acesso: str,
        tp_evento: str,
        desc_evento: str,
        det_evento_xml: str,
        cnpj_autor: str,
        uf: str,
        modelo: str = "55",
        n_seq_evento: int = 1,
        is_production: Optional[bool] = None,
    ) -> SefazEventoResult:
        """Monta, assina e envia o lote de evento <envEvento> versao="1.00"."""
        is_prod = is_production if is_production is not None else settings.is_production
        tp_amb = 1 if is_prod else 2
        c_uf = get_cuf_by_uf(uf)
        dh_evento = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")

        # Id do Evento: ID + tpEvento + chNFe + nSeqEvento (2 dígitos)
        id_evento = f"ID{tp_evento}{chave_acesso}{n_seq_evento:02d}"

        evento = etree.Element(f"{{{NFE_NAMESPACE}}}evento", versao="1.00", nsmap=NFE_NSMAP)
        inf_evento = etree.SubElement(evento, f"{{{NFE_NAMESPACE}}}infEvento", Id=id_evento)

        etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}cOrgao").text = c_uf
        etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}tpAmb").text = str(tp_amb)
        etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}CNPJ").text = "".join(filter(str.isdigit, cnpj_autor))
        etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}chNFe").text = chave_acesso
        etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}dhEvento").text = dh_evento
        etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}tpEvento").text = tp_evento
        etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}nSeqEvento").text = str(n_seq_evento)
        etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}verEvento").text = "1.00"

        det = etree.SubElement(inf_evento, f"{{{NFE_NAMESPACE}}}detEvento", versao="1.00")
        etree.SubElement(det, f"{{{NFE_NAMESPACE}}}descEvento").text = desc_evento

        # Anexa detalhes específicos (xJust ou xCorrecao)
        det_parsed = etree.fromstring(f"<root xmlns='{NFE_NAMESPACE}'>{det_evento_xml}</root>")
        for child in det_parsed:
            det.append(child)

        # Assina o evento na tag infEvento
        evento_assinado = self.signer.sign(evento, reference_tag="infEvento")

        # Monta lote envEvento
        env_evento = etree.Element(f"{{{NFE_NAMESPACE}}}envEvento", versao="1.00", nsmap=NFE_NSMAP)
        etree.SubElement(env_evento, f"{{{NFE_NAMESPACE}}}idLote").text = "1"
        env_evento.append(evento_assinado)

        # Envelopa em SOAP 1.2
        envelope_xml = self.client.wrap_soap12_envelope(
            body_element=env_evento,
            action_namespace=NFE_EVENTO_WS_NS,
        )

        endpoints = resolve_webservices(uf=uf, modelo=modelo, is_production=is_prod)
        url = endpoints.autorizacao.replace("NFeAutorizacao4", "NFeRecepcaoEvento4").replace("nfeautorizacao4", "nferecepcaoevento4")

        res_body = self.client.post_soap(
            url=url,
            envelope_xml=envelope_xml,
            soap_action=f"{NFE_EVENTO_WS_NS}/nfeRecepcaoEvento",
        )

        # Processamento do retEvento
        ret_evento = res_body.find(f".//{{{NFE_NAMESPACE}}}retEvento") or res_body.find(".//retEvento")
        if ret_evento is None:
            c_stat_lote = int(res_body.findtext(f".//{{{NFE_NAMESPACE}}}cStat") or res_body.findtext(".//cStat") or "0")
            x_motivo_lote = res_body.findtext(f".//{{{NFE_NAMESPACE}}}xMotivo") or res_body.findtext(".//xMotivo") or ""
            raise SefazRejectionError(c_stat=c_stat_lote, x_motivo=x_motivo_lote, chave_acesso=chave_acesso)

        inf_ret = ret_evento.find(f"{{{NFE_NAMESPACE}}}infEvento") or ret_evento.find("infEvento")
        c_stat = int(inf_ret.findtext(f"{{{NFE_NAMESPACE}}}cStat") or inf_ret.findtext("cStat") or "0")
        x_motivo = inf_ret.findtext(f"{{{NFE_NAMESPACE}}}xMotivo") or inf_ret.findtext("xMotivo") or ""
        n_prot = inf_ret.findtext(f"{{{NFE_NAMESPACE}}}nProt") or inf_ret.findtext("nProt")
        dh_reg = inf_ret.findtext(f"{{{NFE_NAMESPACE}}}dhRegEvento") or inf_ret.findtext("dhRegEvento")

        # cStat = 135: Evento registrado e vinculado a NF-e
        # cStat = 136: Evento registrado e vinculado a NF-e, mas com lote com erro em outro evento
        is_homologado = (c_stat in (135, 136))

        if not is_homologado:
            raise SefazRejectionError(c_stat=c_stat, x_motivo=x_motivo, chave_acesso=chave_acesso)

        # Constrói o procEventoNFe
        proc_evento = etree.Element(f"{{{NFE_NAMESPACE}}}procEventoNFe", versao="1.00", nsmap=NFE_NSMAP)
        proc_evento.append(evento_assinado)
        proc_evento.append(ret_evento)

        xml_proc_str = etree.tostring(proc_evento, encoding="UTF-8", xml_declaration=True).decode("utf-8")

        return SefazEventoResult(
            c_stat=c_stat,
            x_motivo=x_motivo,
            tp_evento=tp_evento,
            chave_acesso=chave_acesso,
            n_seq_evento=n_seq_evento,
            n_prot=n_prot,
            dh_reg_evento=dh_reg,
            xml_proc_evento=xml_proc_str,
            is_homologado=is_homologado,
        )
