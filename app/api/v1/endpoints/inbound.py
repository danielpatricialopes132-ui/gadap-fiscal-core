"""Endpoints REST da API para Inbound DF-e e Manifestação do Destinatário (Fase 10).

Rotas:
- POST /api/v1/fiscal/inbound/sincronizar/{empresa_id}: Consulta incremental de documentos no AN SEFAZ e persiste em `notas_recebidas`.
- POST /api/v1/fiscal/inbound/{chave}/manifestar: Envia evento de manifestação com assinatura digital para a SEFAZ.
- GET  /api/v1/fiscal/inbound/notas/{empresa_id}: Listagem com paginação e filtros das notas recebidas de fornecedores.
"""

from typing import Optional, List, Literal
from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.fiscal import Empresa
from app.models.inbound import NotaRecebida
from app.core.config import settings
from app.core.security.certificate import A1CertificateManager
from app.services.sefaz.xml_signer import XmlSigner
from app.services.sefaz.mtls_client import SefazMtlsClient
from app.services.sefaz.distribuicao_dfe import SefazDistribuicaoDFeService
from app.services.sefaz.manifestacao_destinatario import SefazManifestacaoDestinatarioService
from app.services.storage.supabase_storage import SupabaseStorageService

logger = logging.getLogger("gadap.api.inbound")

router = APIRouter(prefix="/api/v1/fiscal/inbound", tags=["Inbound DF-e & Manifestação"])


class SincronizacaoResponse(BaseModel):
    sucesso: bool
    empresa_id: str
    cnpj: str
    c_stat: int
    x_motivo: str
    ult_nsu: str
    max_nsu: str
    novos_documentos: int
    mensagem: str


class ManifestacaoInput(BaseModel):
    tipo_evento: Literal["210200", "210210", "210220", "210240"] = Field(
        ...,
        description="210200=Confirmação, 210210=Ciência, 210220=Desconhecimento, 210240=Operação não Realizada",
        examples=["210210"],
    )
    justificativa: Optional[str] = Field(
        None,
        description="Obrigatória para operação não realizada (210240), mínimo 15 caracteres.",
    )


class ManifestacaoResponse(BaseModel):
    sucesso: bool
    chave_acesso: str
    c_stat: int
    x_motivo: str
    protocolo: Optional[str] = None
    descricao_evento: str
    novo_status_manifestacao: str


class NotaRecebidaItem(BaseModel):
    id: str
    chave_acesso: str
    cnpj_emitente: str
    nome_emitente: Optional[str] = None
    valor_total: float
    data_emissao: Optional[str] = None
    nsu: str
    status_manifestacao: str
    tipo_conteudo: str
    storage_url: Optional[str] = None


class ListagemNotasRecebidasResponse(BaseModel):
    total: int
    pagina: int
    limite: int
    itens: List[NotaRecebidaItem]


@router.post(
    "/sincronizar/{empresa_id}",
    response_model=SincronizacaoResponse,
    summary="Sincroniza Documentos Recebidos no Ambiente Nacional (NFeDistribuicaoDFe)",
    description="Consulta o Ambiente Nacional da SEFAZ para baixar resumos e XMLs de notas emitidas contra o CNPJ da empresa.",
)
def sincronizar_documentos_recebidos(
    empresa_id: str,
    db: Session = Depends(get_db_session),
) -> SincronizacaoResponse:
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa com id {empresa_id} não encontrada.",
        )

    # Localiza o último NSU salvo no banco de dados para esta empresa
    ultima_nota = (
        db.query(NotaRecebida)
        .filter(NotaRecebida.empresa_id == empresa_id)
        .order_by(NotaRecebida.nsu.desc())
        .first()
    )
    ult_nsu = ultima_nota.nsu if ultima_nota else "0"

    # Inicializa cliente mTLS se certificado configurado
    cert_bytes = settings.get_certificate_bytes()
    mtls_client = None
    if cert_bytes and settings.CERTIFICATE_PASSWORD:
        try:
            mtls_client = SefazMtlsClient(cert_bytes=cert_bytes, cert_password=settings.CERTIFICATE_PASSWORD)
        except Exception as e:
            logger.warning(f"Não foi possível inicializar mTLS client: {e}")

    service = SefazDistribuicaoDFeService(mtls_client=mtls_client)
    resultado = service.consultar(cnpj=empresa.cnpj, ult_nsu=ult_nsu)

    storage = SupabaseStorageService()
    novos_docs_count = 0

    for doc in resultado.documentos:
        if not doc.chave_acesso:
            continue

        # Verifica se já existe nota gravada
        existente = db.query(NotaRecebida).filter(NotaRecebida.chave_acesso == doc.chave_acesso).first()
        
        # Salva o XML no storage
        xml_path = f"inbound/{empresa.cnpj}/{doc.chave_acesso}.xml"
        try:
            storage_path = storage.salvar_xml_autorizado(doc.chave_acesso, doc.xml_conteudo)
            storage_url = storage.obter_url_download_temporaria(storage_path)
        except Exception:
            storage_path = xml_path
            storage_url = None

        data_emi_dt = None
        if doc.data_emissao:
            try:
                data_emi_dt = datetime.fromisoformat(doc.data_emissao)
            except Exception:
                data_emi_dt = datetime.now(timezone.utc)

        if not existente:
            nova = NotaRecebida(
                empresa_id=empresa.id,
                chave_acesso=doc.chave_acesso,
                cnpj_emitente=doc.cnpj_emitente or "00000000000000",
                nome_emitente=doc.nome_emitente or "Fornecedor",
                valor_total=doc.valor_total,
                data_emissao=data_emi_dt,
                nsu=doc.nsu,
                status_manifestacao="SEM_MANIFESTACAO",
                tipo_conteudo=doc.tipo_documento,
                xml_completo_path=storage_path,
                storage_url=storage_url,
            )
            db.add(nova)
            novos_docs_count += 1
        else:
            # Atualiza caso tenhamos recebido o XML COMPLETO após prévio RESUMO
            if doc.tipo_documento == "COMPLETO" and existente.tipo_conteudo != "COMPLETO":
                existente.tipo_conteudo = "COMPLETO"
                existente.xml_completo_path = storage_path
                existente.storage_url = storage_url
                if doc.valor_total > 0:
                    existente.valor_total = doc.valor_total

    db.commit()

    return SincronizacaoResponse(
        sucesso=True,
        empresa_id=empresa.id,
        cnpj=empresa.cnpj,
        c_stat=resultado.c_stat,
        x_motivo=resultado.x_motivo,
        ult_nsu=resultado.ult_nsu,
        max_nsu=resultado.max_nsu,
        novos_documentos=novos_docs_count,
        mensagem=f"Sincronização concluída. {novos_docs_count} novo(s) documento(s) capturado(s).",
    )


@router.post(
    "/{chave}/manifestar",
    response_model=ManifestacaoResponse,
    summary="Registra Evento de Manifestação do Destinatário na SEFAZ",
    description="Permite enviar Ciência da Emissão (210210), Confirmação (210200), Desconhecimento (210220) ou Operação não Realizada (210240).",
)
def manifestar_documento(
    chave: str,
    payload: ManifestacaoInput,
    db: Session = Depends(get_db_session),
) -> ManifestacaoResponse:
    if len(chave) != 44 or not chave.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chave de acesso inválida. Deve conter 44 dígitos.",
        )

    nota = db.query(NotaRecebida).filter(NotaRecebida.chave_acesso == chave).first()
    if not nota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento recebido com chave {chave} não encontrado.",
        )

    empresa = db.query(Empresa).filter(Empresa.id == nota.empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empresa associada ao documento não encontrada.",
        )

    # Configuração dos componentes de assinatura e mTLS
    cert_bytes = settings.get_certificate_bytes()
    signer = None
    mtls_client = None
    if cert_bytes and settings.CERTIFICATE_PASSWORD:
        try:
            cert_mgr = A1CertificateManager(pfx_data=cert_bytes, password=settings.CERTIFICATE_PASSWORD)
            signer = XmlSigner(private_key=cert_mgr.private_key, x509_cert_der=cert_mgr.certificate_der)
            mtls_client = SefazMtlsClient(cert_bytes=cert_bytes, cert_password=settings.CERTIFICATE_PASSWORD)
        except Exception as e:
            logger.warning(f"Certificado não inicializado para manifestação: {e}")

    service = SefazManifestacaoDestinatarioService(signer=signer, mtls_client=mtls_client)
    
    try:
        resultado = service.registrar_manifestacao(
            chave_acesso=chave,
            cnpj_destinatario=empresa.cnpj,
            tipo_evento=payload.tipo_evento,
            justificativa=payload.justificativa,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    # Mapeamento do novo status
    status_map = {
        "210200": "CONFIRMADA",
        "210210": "CIENCIA",
        "210220": "DESCONHECIDA",
        "210240": "NAO_REALIZADA",
    }
    novo_status = status_map.get(payload.tipo_evento, "MANIFESTADA")

    if resultado.get("sucesso"):
        nota.status_manifestacao = novo_status
        nota.protocolo_manifestacao = resultado.get("protocolo")
        nota.data_manifestacao = datetime.now(timezone.utc)
        db.commit()

        return ManifestacaoResponse(
            sucesso=True,
            chave_acesso=chave,
            c_stat=resultado["c_stat"],
            x_motivo=resultado["x_motivo"],
            protocolo=resultado.get("protocolo"),
            descricao_evento=resultado["descricao_evento"],
            novo_status_manifestacao=novo_status,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "erro": "SEFAZ_EVENT_REJECTION",
                "cStat": resultado.get("c_stat"),
                "xMotivo": resultado.get("x_motivo"),
            },
        )


@router.get(
    "/notas/{empresa_id}",
    response_model=ListagemNotasRecebidasResponse,
    summary="Listagem das Notas Recebidas de Fornecedores",
    description="Permite ao ERP e Fiscal Hub consultar documentos emitidos contra o CNPJ da empresa com filtros de status.",
)
def listar_notas_recebidas(
    empresa_id: str,
    status_manifestacao: Optional[str] = Query(None, description="SEM_MANIFESTACAO, CIENCIA, CONFIRMADA, etc."),
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
) -> ListagemNotasRecebidasResponse:
    query = db.query(NotaRecebida).filter(NotaRecebida.empresa_id == empresa_id)
    if status_manifestacao:
        query = query.filter(NotaRecebida.status_manifestacao == status_manifestacao)

    total = query.count()
    offset = (pagina - 1) * limite
    registros = query.order_by(NotaRecebida.created_at.desc()).offset(offset).limit(limite).all()

    itens = [
        NotaRecebidaItem(
            id=r.id,
            chave_acesso=r.chave_acesso,
            cnpj_emitente=r.cnpj_emitente,
            nome_emitente=r.nome_emitente,
            valor_total=float(r.valor_total),
            data_emissao=r.data_emissao.isoformat() if r.data_emissao else None,
            nsu=r.nsu,
            status_manifestacao=r.status_manifestacao,
            tipo_conteudo=r.tipo_conteudo,
            storage_url=r.storage_url,
        )
        for r in registros
    ]

    return ListagemNotasRecebidasResponse(
        total=total,
        pagina=pagina,
        limite=limite,
        itens=itens,
    )
