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
    danfe_pdf_bytes = None
    try:
        danfe_pdf_bytes = DanfePdfGenerator.generate_danfe_pdf(
            xml_input=xml_final,
            force_homologacao=not settings.is_production,
        )
        danfe_b64 = base64.b64encode(danfe_pdf_bytes).decode("utf-8")
    except Exception:
        danfe_b64 = None

    xml_b64 = base64.b64encode(xml_final.encode("utf-8")).decode("utf-8")

    # 5. Persistência e Storage local / Supabase
    try:
        from app.services.storage import FiscalStorageService
        storage_svc = FiscalStorageService()
        tot_liquido = sum(float(it.valor_total_liquido) for it in payload.itens)
        storage_svc.registrar_documento(
            tipo_documento=tipo.value,
            chave_acesso=chave_acesso,
            numero=payload.numero,
            serie=payload.serie,
            emitente_cnpj=payload.emitente.cnpj,
            destinatario_doc=payload.destinatario.cpf_cnpj if payload.destinatario else None,
            valor_total=tot_liquido,
            status="AUTORIZADA",
            xml_conteudo=xml_final,
            pdf_bytes=danfe_pdf_bytes,
        )
    except Exception:
        pass

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


# ------------------------------------------------------------------------------
# Inutilização de Faixa Numérica (NFeInutilizacao4)
# ------------------------------------------------------------------------------
class InutilizacaoRequest(BaseModel):
    uf: str = Field(..., min_length=2, max_length=2, description="Sigla da UF")
    ano: int = Field(..., ge=2000, le=2100, description="Ano com 4 dígitos")
    cnpj: str = Field(..., min_length=14, max_length=14, description="CNPJ do emitente (apenas números)")
    modelo: Literal["55", "65"] = Field(default="55", description="55 (NF-e) ou 65 (NFC-e)")
    serie: int = Field(..., ge=1, le=999, description="Série da numeração")
    numero_inicial: int = Field(..., ge=1, le=999999999)
    numero_final: int = Field(..., ge=1, le=999999999)
    justificativa: str = Field(..., min_length=15, max_length=255, description="Mínimo 15 caracteres")


class InutilizacaoResponse(BaseModel):
    sucesso: bool
    c_stat: int
    x_motivo: str
    protocolo: Optional[str] = None
    xml_proc_inut_b64: Optional[str] = None


@router.post(
    "/inutilizar",
    response_model=InutilizacaoResponse,
    summary="Inutilização de Numeração (NFeInutilizacao4)",
    description="Inutiliza faixas numéricas de NF-e e NFC-e que não foram utilizadas por quebra de sequência ou erro.",
)
def inutilizar_numeracao(req: InutilizacaoRequest) -> InutilizacaoResponse:
    from app.services.sefaz.inutilizacao import SefazInutilizacaoService
    from app.services.sefaz.mtls_client import SefazMtlsClient

    cert_bytes = settings.get_certificate_bytes()
    mtls_client = None
    signer = None
    if cert_bytes and settings.CERTIFICATE_PASSWORD:
        cert_mgr = A1CertificateManager(pfx_data=cert_bytes, password=settings.CERTIFICATE_PASSWORD)
        signer = XmlSigner(private_key=cert_mgr.private_key, x509_cert_der=cert_mgr.certificate_der)
        mtls_client = SefazMtlsClient(cert_bytes=cert_bytes, cert_password=settings.CERTIFICATE_PASSWORD)

    service = SefazInutilizacaoService(mtls_client=mtls_client, signer=signer)
    res = service.inutilizar_faixa(
        uf=req.uf.upper(),
        ano=req.ano,
        cnpj=req.cnpj,
        modelo=req.modelo,
        serie=req.serie,
        n_nf_ini=req.numero_inicial,
        n_nf_fin=req.numero_final,
        justificativa=req.justificativa,
    )
    b64_proc = base64.b64encode(res.xml_proc_inut.encode("utf-8")).decode("utf-8") if res.xml_proc_inut else None
    return InutilizacaoResponse(
        sucesso=res.is_homologado,
        c_stat=res.c_stat,
        x_motivo=res.x_motivo,
        protocolo=res.n_prot,
        xml_proc_inut_b64=b64_proc,
    )


# ------------------------------------------------------------------------------
# Distribuição DF-e e Manifestação do Destinatário (NFeDistribuicaoDFe)
# ------------------------------------------------------------------------------
class DistribuicaoConsultaResponse(BaseModel):
    c_stat: int
    x_motivo: str
    ult_nsu: str
    max_nsu: str
    quantidade_documentos: int
    documentos: list


class ManifestacaoRequest(BaseModel):
    chave_acesso: str = Field(..., min_length=44, max_length=44, description="Chave de 44 dígitos da NF-e")
    cnpj_destinatario: str = Field(..., min_length=14, max_length=14, description="CNPJ do destinatário")
    tipo_evento: Literal["210200", "210210", "210220", "210240"] = Field(
        default="210210",
        description="210200=Confirmação, 210210=Ciência da Emissão, 210220=Desconhecimento, 210240=Não Realizada",
    )
    justificativa: Optional[str] = Field(None, max_length=255, description="Obrigatória para operação não realizada")


@router.get(
    "/distribuicao/consultar",
    response_model=DistribuicaoConsultaResponse,
    summary="Consulta de Documentos Emitidos contra o CNPJ (NFeDistribuicaoDFe)",
    description="Consulta o Ambiente Nacional para baixar resumos e XMLs completos das notas emitidas contra o CNPJ da empresa.",
)
def consultar_distribuicao_dfe(
    cnpj: str = Query(..., description="CNPJ do destinatário (14 dígitos)"),
    ult_nsu: str = Query("0", description="Último NSU processado pelo ERP"),
    ch_nfe: Optional[str] = Query(None, description="Chave de acesso específica (opcional)"),
) -> DistribuicaoConsultaResponse:
    from app.services.sefaz.distribuicao import SefazDistribuicaoDFeService
    from app.services.sefaz.mtls_client import SefazMtlsClient

    cert_bytes = settings.get_certificate_bytes()
    mtls_client = None
    if cert_bytes and settings.CERTIFICATE_PASSWORD:
        mtls_client = SefazMtlsClient(cert_bytes=cert_bytes, cert_password=settings.CERTIFICATE_PASSWORD)

    service = SefazDistribuicaoDFeService(mtls_client=mtls_client)
    res = service.consultar_dfe(cnpj=cnpj, ult_nsu=ult_nsu, ch_nfe=ch_nfe)

    docs_formatados = [
        {
            "nsu": d.nsu,
            "schema": d.schema,
            "chave_acesso": d.chave_acesso,
            "resumo": d.resumo,
            "xml_b64": base64.b64encode(d.xml_conteudo.encode("utf-8")).decode("utf-8"),
        }
        for d in res.documentos
    ]

    return DistribuicaoConsultaResponse(
        c_stat=res.c_stat,
        x_motivo=res.x_motivo,
        ult_nsu=res.ult_nsu,
        max_nsu=res.max_nsu,
        quantidade_documentos=len(docs_formatados),
        documentos=docs_formatados,
    )


@router.post(
    "/distribuicao/manifestar",
    summary="Manifestação do Destinatário (Ciência, Confirmação, etc.)",
    description="Envia eventos de Ciência da Emissão ou Confirmação para liberar o download do XML completo do fornecedor.",
)
def manifestar_destinatario_endpoint(req: ManifestacaoRequest):
    from app.services.sefaz.distribuicao import SefazDistribuicaoDFeService
    from app.services.sefaz.mtls_client import SefazMtlsClient

    cert_bytes = settings.get_certificate_bytes()
    mtls_client = None
    signer = None
    if cert_bytes and settings.CERTIFICATE_PASSWORD:
        cert_mgr = A1CertificateManager(pfx_data=cert_bytes, password=settings.CERTIFICATE_PASSWORD)
        signer = XmlSigner(private_key=cert_mgr.private_key, x509_cert_der=cert_mgr.certificate_der)
        mtls_client = SefazMtlsClient(cert_bytes=cert_bytes, cert_password=settings.CERTIFICATE_PASSWORD)

    service = SefazDistribuicaoDFeService(mtls_client=mtls_client, signer=signer)
    return service.manifestar_destinatario(
        chave_acesso=req.chave_acesso,
        cnpj_destinatario=req.cnpj_destinatario,
        tipo_evento=req.tipo_evento,
        justificativa=req.justificativa,
    )

