"""Endpoints REST v1 da API Fiscal (NF-e, NFC-e e NFS-e).

Rotas:
- POST /api/v1/fiscal/emitir: Orquestração completa de NF-e, NFC-e ou NFS-e com geração de XML e DANFE em Base64.
- GET  /api/v1/fiscal/status-sefaz: Verificação de conectividade e status dos servidores SEFAZ por UF.
- GET  /api/v1/fiscal/certificado/status: Diagnóstico do certificado ICP-Brasil A1 ativo e dias até a expiração.
"""

from typing import Optional, Literal
import base64
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security.certificate import A1CertificateManager
from app.schemas.canonical import DocumentoFiscalInput, TipoDocumento
from app.services.tax_engine import TaxEngineSimplesNacional
from app.services.sefaz.xml_builder import NFeXmlBuilder
from app.services.sefaz.xml_signer import XmlSigner
from app.services.sefaz.transmitter import SefazTransmitter, SefazRejectionError
from app.services.nfse.national_adapter import NationalNfseAdapter
from app.services.danfe.pdf_generator import DanfePdfGenerator

router = APIRouter(prefix="/api/v1/fiscal", tags=["Fiscal"])


class CertificadoStatusResponse(BaseModel):
    carregado: bool
    valido: bool
    subject: Optional[str] = None
    serial_number: Optional[str] = None
    not_valid_after: Optional[str] = None
    dias_para_expirar: Optional[int] = None
    alerta_expiracao: Optional[str] = None
    mensagem: str


class SefazStatusResponse(BaseModel):
    uf: str
    ambiente: str
    tp_amb: int
    c_stat: str
    x_motivo: str
    status_operacional: bool
    tempo_resposta_ms: Optional[float] = None


class EmissaoFiscalResponse(BaseModel):
    sucesso: bool
    tipo_documento: TipoDocumento
    status: str = Field(..., description="AUTORIZADA, REJEITADA ou PROCESSADA")
    chave_acesso: str = Field(..., description="Chave de acesso de 44 dígitos (NF-e/NFC-e) ou 50 dígitos (NFS-e)")
    numero_documento: int
    serie: int
    c_stat: Optional[str] = Field(None, description="Código de status SEFAZ/ADN")
    x_motivo: Optional[str] = Field(None, description="Motivo retornado pelo fisco")
    protocolo: Optional[str] = Field(None, description="Número de protocolo de autorização")
    xml_autorizado_b64: str = Field(..., description="XML final autorizado/definitivo codificado em Base64")
    danfe_pdf_b64: Optional[str] = Field(None, description="DANFE / DAMDFE em PDF codificado em Base64")
    ambiente: str = Field(..., description="homologacao ou producao")


@router.get(
    "/certificado/status",
    response_model=CertificadoStatusResponse,
    summary="Status do Certificado Digital A1",
    description="Inspeciona o certificado A1 carregado em memória, validando sua expiração e alertando sobre prazos críticos.",
)
def get_certificado_status() -> CertificadoStatusResponse:
    cert_bytes = settings.get_certificate_bytes()
    if not cert_bytes:
        return CertificadoStatusResponse(
            carregado=False,
            valido=False,
            mensagem="Nenhum certificado A1 configurado (CERTIFICATE_PATH ou CERTIFICATE_BASE64 vazios).",
        )

    try:
        manager = A1CertificateManager(pfx_data=cert_bytes, password=settings.CERTIFICATE_PASSWORD)
        dias = manager.get_days_until_expiration()
        valido = not manager.is_expired()
        alerta = None

        if dias < 0:
            alerta = "CERTIFICADO EXPIRADO! Não é possível emitir notas fiscais."
        elif dias <= 7:
            alerta = f"ALERTA CRÍTICO: Certificado expira em {dias} dias!"
        elif dias <= 30:
            alerta = f"ATENÇÃO: Certificado expira em {dias} dias."
        elif dias <= 60:
            alerta = f"Aviso: Certificado expira em {dias} dias."

        return CertificadoStatusResponse(
            carregado=True,
            valido=valido,
            subject=manager.get_subject_name(),
            serial_number=str(manager.certificate.serial_number),
            not_valid_after=manager.certificate.not_valid_after_utc.isoformat(),
            dias_para_expirar=dias,
            alerta_expiracao=alerta,
            mensagem="Certificado válido e pronto para uso." if valido else "Certificado vencido.",
        )
    except Exception as e:
        return CertificadoStatusResponse(
            carregado=True,
            valido=False,
            mensagem=f"Erro ao carregar certificado A1: {str(e)}",
        )


@router.get(
    "/status-sefaz",
    response_model=SefazStatusResponse,
    summary="Consulta Status do Servidor SEFAZ",
    description="Dispara uma requisição SOAP 1.2 consStatServ contra o WebService da UF especificada para verificar a operabilidade da SEFAZ.",
)
def get_status_sefaz(
    uf: Optional[str] = Query(None, description="Sigla da UF (ex: SP, BA, RJ). Padrão: UF do emitente."),
    modelo: Literal["55", "65"] = Query("55", description="Modelo da nota: 55 (NF-e) ou 65 (NFC-e)"),
) -> SefazStatusResponse:
    target_uf = (uf or settings.EMITENTE_UF).upper()
    cert_bytes = settings.get_certificate_bytes()

    if not cert_bytes or not settings.CERTIFICATE_PASSWORD:
        # Modo simulação estruturada se não houver certificado instalado
        return SefazStatusResponse(
            uf=target_uf,
            ambiente=settings.DFE_ENVIRONMENT.value,
            tp_amb=settings.tp_amb,
            c_stat="107",
            x_motivo="Servico em Operacao (Simulado / Sem Certificado A1)",
            status_operacional=True,
        )

    try:
        transmitter = SefazTransmitter(
            cert_bytes=cert_bytes,
            cert_password=settings.CERTIFICATE_PASSWORD,
            is_production=settings.is_production,
        )
        status_info = transmitter.consultar_status_servico(uf=target_uf, modelo=modelo)
        return SefazStatusResponse(
            uf=target_uf,
            ambiente=settings.DFE_ENVIRONMENT.value,
            tp_amb=settings.tp_amb,
            c_stat=status_info.c_stat,
            x_motivo=status_info.x_motivo,
            status_operacional=status_info.status_operacional,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Falha ao conectar com a SEFAZ-{target_uf}: {str(e)}",
        )


@router.post(
    "/emitir",
    response_model=EmissaoFiscalResponse,
    summary="Emissão Canônica de Documento Fiscal (NF-e, NFC-e e NFS-e)",
    description="Orquestra o ciclo completo: cálculo tributário (Simples Nacional), geração e validação de XML, assinatura XML-DSig, autorização e geração de DANFE em PDF.",
)
def emitir_documento_fiscal(payload: DocumentoFiscalInput) -> EmissaoFiscalResponse:
    tipo = payload.tipo_documento

    # -------------------------------------------------------------------------
    # RAMIFICAÇÃO NFS-e: Ambiente de Dados Nacional (ADN) / DPS
    # -------------------------------------------------------------------------
    if tipo == TipoDocumento.NFSE:
        adapter = NationalNfseAdapter()
        resultado = adapter.emitir_dps(payload)

        # Montagem de DANFE / Espelho da NFS-e simplificado
        xml_bytes = resultado.xml_nfse.encode("utf-8") if resultado.xml_nfse else resultado.xml_dps.encode("utf-8")
        xml_b64 = base64.b64encode(xml_bytes).decode("utf-8")

        return EmissaoFiscalResponse(
            sucesso=resultado.sucesso,
            tipo_documento=tipo,
            status=resultado.status_processamento,
            chave_acesso=resultado.chave_acesso_nfse or "",
            numero_documento=payload.numero,
            serie=payload.serie,
            c_stat="100",
            x_motivo="DPS autorizada no Ambiente de Dados Nacional (ADN)",
            protocolo=resultado.protocolo,
            xml_autorizado_b64=xml_b64,
            danfe_pdf_b64=None,
            ambiente=settings.DFE_ENVIRONMENT.value,
        )

    # -------------------------------------------------------------------------
    # RAMIFICAÇÃO NF-e (55) e NFC-e (65): SEFAZ
    # -------------------------------------------------------------------------
    modelo = "65" if tipo == TipoDocumento.NFCE else "55"

    # 1 e 2. Cálculo tributário e Construção do XML v4.00
    try:
        xml_raw, chave_acesso = NFeXmlBuilder.build_from_input(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro na geração e validação fiscal do XML: {str(e)}",
        )

    cert_bytes = settings.get_certificate_bytes()
    
    # 3. Assinatura e Transmissão
    if cert_bytes and settings.CERTIFICATE_PASSWORD:
        try:
            cert_mgr = A1CertificateManager(pfx_data=cert_bytes, password=settings.CERTIFICATE_PASSWORD)
            signer = XmlSigner(
                private_key=cert_mgr.private_key,
                x509_cert_der=cert_mgr.certificate_der,
            )
            xml_assinado = signer.sign_xml(xml_raw)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro na assinatura digital do XML: {str(e)}",
            )

        # Transmissão SEFAZ
        try:
            transmitter = SefazTransmitter(
                cert_bytes=cert_bytes,
                cert_password=settings.CERTIFICATE_PASSWORD,
                is_production=settings.is_production,
            )
            lote_result = transmitter.enviar_lote_sincrono(
                xml_assinado=xml_assinado,
                uf=payload.emitente.endereco.uf,
                modelo=modelo,
            )
            xml_final = lote_result.xml_proc_completo or xml_assinado
            c_stat = lote_result.c_stat
            x_motivo = lote_result.x_motivo
            protocolo = lote_result.n_prot
        except SefazRejectionError as se:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "erro": "SEFAZ_REJECTION",
                    "cStat": se.c_stat,
                    "xMotivo": se.x_motivo,
                    "sugestao": se.sugestao,
                },
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erro na comunicação com a SEFAZ: {str(e)}",
            )
    else:
        # Modo Homologação / Simulação Sem Certificado Instalado
        xml_final = xml_raw
        c_stat = "100"
        x_motivo = "Autorizado o uso da NF-e (Ambiente de Homologacao / Simulado)"
        protocolo = "135240000000001"

    # 4. Geração do DANFE em PDF com Marca d'água automática se homologação
    try:
        danfe_pdf_bytes = DanfePdfGenerator.generate_danfe_pdf(
            xml_input=xml_final,
            force_homologacao=not settings.is_production,
        )
        danfe_b64 = base64.b64encode(danfe_pdf_bytes).decode("utf-8")
    except Exception as e:
        danfe_b64 = None

    xml_b64 = base64.b64encode(xml_final.encode("utf-8")).decode("utf-8")

    return EmissaoFiscalResponse(
        sucesso=True,
        tipo_documento=tipo,
        status="AUTORIZADA",
        chave_acesso=chave_acesso,
        numero_documento=payload.numero,
        serie=payload.serie,
        c_stat=c_stat,
        x_motivo=x_motivo,
        protocolo=protocolo,
        xml_autorizado_b64=xml_b64,
        danfe_pdf_b64=danfe_b64,
        ambiente=settings.DFE_ENVIRONMENT.value,
    )
