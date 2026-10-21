"""Rotas da API FastAPI para o GADAP Fiscal Core: emissão, status, cancelamento, CC-e e DANFE PDF."""

import base64
from typing import Optional
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.schemas.canonical import DocumentoFiscalInput
from app.services.tax_engine import TaxEngineSimplesNacional
from app.services.sefaz.xml_builder import NFeXmlBuilder
from app.services.sefaz.xml_signer import XmlSigner
from app.services.sefaz.qrcode_generator import QRCodeGenerator
from app.services.sefaz.xsd_validator import XsdValidator, XsdValidationError
from app.services.sefaz.mtls_client import SefazMtlsClient
from app.services.sefaz.transmitter import SefazTransmitter, SefazRejectionError
from app.services.sefaz.events import SefazEventManager
from app.services.sefaz.danfe_generator import DanfePdfGenerator
from app.core.security.certificate import A1CertificateManager
from app.core.config import settings


router = APIRouter(prefix="/api/v1/dfe", tags=["Documentos Fiscais"])


def get_cert_manager() -> A1CertificateManager:
    """Helper para instanciar o gerenciador de certificado digital a partir do ambiente."""
    cert_bytes = settings.get_certificate_bytes()
    if not cert_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificado digital A1 não configurado no ambiente (.env). Informe CERTIFICATE_PATH ou CERTIFICATE_BASE64.",
        )
    return A1CertificateManager(pfx_data=cert_bytes, password=settings.CERTIFICATE_PASSWORD)


# Schemas de Request / Response
class StatusServicoRequest(BaseModel):
    uf: str = Field(default="SP", min_length=2, max_length=2)
    modelo: str = Field(default="55", pattern="^(55|65)$")


class EmissaoResponse(BaseModel):
    status: str
    chave_acesso: str
    numero_protocolo: Optional[str] = None
    data_recebimento: Optional[str] = None
    xml_autorizado_b64: str
    c_stat: int
    motivo: str


class CancelamentoRequest(BaseModel):
    chave_acesso: str = Field(..., min_length=44, max_length=44)
    protocolo_autorizacao: str = Field(..., min_length=15, max_length=15)
    justificativa: str = Field(..., min_length=15, max_length=255)
    cnpj_emitente: str = Field(..., min_length=14, max_length=14)
    uf: str = Field(default="SP", min_length=2, max_length=2)
    modelo: str = Field(default="55", pattern="^(55|65)$")


class CartaCorrecaoRequest(BaseModel):
    chave_acesso: str = Field(..., min_length=44, max_length=44)
    texto_correcao: str = Field(..., min_length=15, max_length=1000)
    cnpj_emitente: str = Field(..., min_length=14, max_length=14)
    uf: str = Field(default="SP", min_length=2, max_length=2)
    modelo: str = Field(default="55", pattern="^(55|65)$")
    sequencia: int = Field(default=1, ge=1, le=20)


class EventoResponse(BaseModel):
    status: str
    chave_acesso: str
    protocolo_evento: Optional[str] = None
    data_registro: Optional[str] = None
    c_stat: int
    motivo: str
    xml_proc_evento_b64: str


class DanfeRequest(BaseModel):
    xml_b64: str = Field(..., description="XML autorizado (<nfeProc> ou <NFe>) em Base64")


@router.post("/status-servico")
def consultar_status(req: StatusServicoRequest):
    """Consulta o status operacional do WebService SEFAZ da respectiva UF."""
    cert = get_cert_manager()
    client = SefazMtlsClient(cert)
    transmitter = SefazTransmitter(client)

    result = transmitter.consultar_status_servico(uf=req.uf, modelo=req.modelo)
    return {
        "uf": req.uf,
        "operacional": result.is_operacional,
        "c_stat": result.c_stat,
        "motivo": result.x_motivo,
        "tempo_medio_resposta_segundos": result.t_med,
    }


@router.post("/emitir", response_model=EmissaoResponse)
def emitir_documento_fiscal(doc: DocumentoFiscalInput):
    """Pipeline completo de emissão síncrona:

    1. Processamento fiscal Simples Nacional (CRT 1)
    2. Geração da chave e árvore XML v4.00
    3. Validação local contra o Schema XSD
    4. Assinatura digital XML-DSig ICP-Brasil
    5. Injeção de QR Code v2.0 (se NFC-e)
    6. Handshake mTLS e transmissão síncrona SOAP 1.2
    7. Montagem do XML definitivo <nfeProc>
    """
    cert = get_cert_manager()

    # 1. Regras fiscais
    doc_proc = TaxEngineSimplesNacional.process(doc)

    # 2. Construtor XML
    builder = NFeXmlBuilder(doc_proc)
    raw_xml_element = builder.build()

    # 3. Validação XSD prévia
    try:
        XsdValidator.assert_valid(raw_xml_element)
    except XsdValidationError as xsd_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Inconsistência cadastral no Schema XML: {xsd_err}",
        )

    # 4. Assinatura Digital
    signer = XmlSigner(cert)
    signed_xml = signer.sign(raw_xml_element)

    # 5. Injeção do QR Code se for NFC-e
    if doc.tipo_documento.value == "NFCE":
        signed_xml = QRCodeGenerator.inject_qr_code_into_xml(
            xml_input=signed_xml,
            uf_emitente=doc.emitente.endereco.uf,
        )

    # 6. Transmissão SEFAZ
    client = SefazMtlsClient(cert)
    transmitter = SefazTransmitter(client)

    modelo = "65" if doc.tipo_documento.value == "NFCE" else "55"
    uf = doc.emitente.endereco.uf

    try:
        res = transmitter.enviar_lote_sincrono(
            xml_assinado=signed_xml,
            uf=uf,
            modelo=modelo,
        )
    except SefazRejectionError as rej:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "c_stat": rej.c_stat,
                "motivo": rej.x_motivo,
                "chave_acesso": rej.chave_acesso,
                "sugestao": rej.sugestao,
            },
        )

    xml_b64 = base64.b64encode((res.xml_proc or "").encode("utf-8")).decode("ascii")

    return EmissaoResponse(
        status="AUTORIZADO",
        chave_acesso=res.chave_acesso,
        numero_protocolo=res.n_prot,
        data_recebimento=res.dh_recbto,
        xml_autorizado_b64=xml_b64,
        c_stat=res.c_stat,
        motivo=res.x_motivo,
    )


@router.post("/cancelar", response_model=EventoResponse)
def cancelar_documento(req: CancelamentoRequest):
    """Cancela uma NF-e ou NFC-e previamente autorizada."""
    cert = get_cert_manager()
    client = SefazMtlsClient(cert)
    signer = XmlSigner(cert)
    events = SefazEventManager(client, signer)

    try:
        res = events.cancelar_documento(
            chave_acesso=req.chave_acesso,
            n_protocolo_autorizacao=req.protocolo_autorizacao,
            justificativa=req.justificativa,
            cnpj_emitente=req.cnpj_emitente,
            uf=req.uf,
            modelo=req.modelo,
        )
    except SefazRejectionError as rej:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"c_stat": rej.c_stat, "motivo": rej.x_motivo, "sugestao": rej.sugestao},
        )

    b64_proc = base64.b64encode((res.xml_proc_evento or "").encode("utf-8")).decode("ascii")

    return EventoResponse(
        status="HOMOLOGADO",
        chave_acesso=res.chave_acesso,
        protocolo_evento=res.n_prot,
        data_registro=res.dh_reg_evento,
        c_stat=res.c_stat,
        motivo=res.x_motivo,
        xml_proc_evento_b64=b64_proc,
    )


@router.post("/carta-correcao", response_model=EventoResponse)
def emitir_carta_correcao(req: CartaCorrecaoRequest):
    """Emite Carta de Correção Eletrônica (CC-e) para retificar dados de uma NF-e."""
    cert = get_cert_manager()
    client = SefazMtlsClient(cert)
    signer = XmlSigner(cert)
    events = SefazEventManager(client, signer)

    try:
        res = events.carta_correcao(
            chave_acesso=req.chave_acesso,
            texto_correcao=req.texto_correcao,
            cnpj_emitente=req.cnpj_emitente,
            uf=req.uf,
            modelo=req.modelo,
            n_seq_evento=req.sequencia,
        )
    except SefazRejectionError as rej:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"c_stat": rej.c_stat, "motivo": rej.x_motivo, "sugestao": rej.sugestao},
        )

    b64_proc = base64.b64encode((res.xml_proc_evento or "").encode("utf-8")).decode("ascii")

    return EventoResponse(
        status="HOMOLOGADO",
        chave_acesso=res.chave_acesso,
        protocolo_evento=res.n_prot,
        data_registro=res.dh_reg_evento,
        c_stat=res.c_stat,
        motivo=res.x_motivo,
        xml_proc_evento_b64=b64_proc,
    )


@router.post("/danfe/pdf")
def gerar_danfe_pdf(req: DanfeRequest):
    """Gera o arquivo PDF binário do DANFE a partir do XML codificado em Base64."""
    try:
        xml_bytes = base64.b64decode(req.xml_b64)
        pdf_bytes = DanfePdfGenerator.generate_danfe_pdf(xml_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falha ao gerar DANFE PDF: {e}",
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="danfe.pdf"'},
    )
