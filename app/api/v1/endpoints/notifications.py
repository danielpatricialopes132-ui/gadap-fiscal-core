"""Endpoints para Disparo e Reenvio Manual de Notificações Multicanal (WhatsApp Evolution API).

Permite aos operadores do ERP e GADAP Fiscal Hub:
- Reenviar DANFE em PDF e mensagem de autorização via WhatsApp para um número avulso ou do cliente.
- Testar a conectividade e status com a Evolution API.
"""

from typing import Optional
from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.fiscal import DocumentoFiscal, ArquivoFiscal
from app.services.storage.supabase_storage import SupabaseStorageService
from app.services.notifications.evolution_whatsapp import EvolutionWhatsAppClient
from app.core.config import settings

logger = logging.getLogger("gadap.notifications")

router = APIRouter(prefix="/api/v1/fiscal", tags=["Notifications & WhatsApp"])


class ReenviarWhatsAppRequest(BaseModel):
    telefone: str = Field(
        ...,
        description="Número do telefone celular com DDD (ex: '11999998888' ou '+55 11 99999-8888')",
        examples=["11999998888"],
    )
    destinatario_nome: Optional[str] = Field(
        None,
        description="Nome do destinatário para personalizar a saudação (opcional)",
    )


class ReenviarWhatsAppResponse(BaseModel):
    sucesso: bool
    chave_acesso: str
    numero_nota: int
    telefone_destino: str
    message_id: Optional[str] = None
    detalhes: Optional[str] = None


@router.post(
    "/documentos/{chave}/reenviar-whatsapp",
    response_model=ReenviarWhatsAppResponse,
    summary="Reenvio Manual de DANFE via WhatsApp (Evolution API)",
    description=(
        "Dispara o DANFE em PDF da nota fiscal e uma mensagem formatada para o número de WhatsApp informado. "
        "Permite que o operador do ERP reenvie a nota diretamente ao cliente ou contador."
    ),
)
def reenviar_whatsapp_endpoint(
    chave: str,
    payload: ReenviarWhatsAppRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
) -> ReenviarWhatsAppResponse:
    if len(chave) != 44 or not chave.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chave de acesso inválida. Deve conter 44 dígitos numéricos.",
        )

    # 1. Busca documento no banco
    doc = db.query(DocumentoFiscal).filter(DocumentoFiscal.chave_acesso == chave).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento fiscal com chave {chave} não encontrado.",
        )

    if doc.status != "AUTORIZADA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas notas AUTORIZADAS podem ser enviadas por WhatsApp. Status atual: {doc.status}",
        )

    # 2. Localiza arquivo PDF do DANFE
    storage_svc = SupabaseStorageService()
    arq_pdf = next((a for a in doc.arquivos if a.tipo_arquivo == "PDF_DANFE"), None)

    url_pdf = None
    if arq_pdf and arq_pdf.bucket_path:
        url_pdf = storage_svc.obter_url_download_temporaria(arq_pdf.bucket_path, expires_in=7200)
    elif arq_pdf and arq_pdf.storage_url:
        url_pdf = arq_pdf.storage_url

    # Fallback caso o registro no bucket ainda use a chave padrão
    if not url_pdf:
        caminho_esperado = f"pdf/{chave}.pdf"
        url_pdf = storage_svc.obter_url_download_temporaria(caminho_esperado, expires_in=7200)

    # 3. Sanitiza e valida o telefone informado
    try:
        telefone_sanitizado = EvolutionWhatsAppClient.sanitizar_numero(payload.telefone)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de telefone inválido: {str(e)}",
        )

    nome_dest = payload.destinatario_nome or doc.destinatario_nome or "Cliente"
    razao_emit = doc.empresa.razao_social if doc.empresa else "GADAP Fiscal Hub"

    # 4. Envio via Evolution API
    client = EvolutionWhatsAppClient()
    resultado = client.enviar_notificacao_nota_autorizada(
        chave_acesso=doc.chave_acesso,
        numero_nota=doc.numero,
        destinatario_nome=nome_dest,
        telefone=telefone_sanitizado,
        pdf_url=url_pdf,
        razao_social_emitente=razao_emit,
    )

    if resultado.get("sucesso"):
        # Atualiza histórico de notificação
        msg_id = str(resultado.get("message_id") or "")
        doc.whatsapp_telefone = telefone_sanitizado
        doc.whatsapp_notificado_at = datetime.now(timezone.utc)
        doc.whatsapp_message_id = msg_id
        db.commit()

        return ReenviarWhatsAppResponse(
            sucesso=True,
            chave_acesso=doc.chave_acesso,
            numero_nota=doc.numero,
            telefone_destino=telefone_sanitizado,
            message_id=msg_id,
            detalhes="Documento fiscal reenviado com sucesso via WhatsApp.",
        )
    else:
        erro_msg = resultado.get("erro", "Falha de comunicação com a Evolution API")
        logger.error(f"Erro ao reenviar WhatsApp para nota {chave}: {erro_msg}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao disparar mensagem via WhatsApp Evolution API: {erro_msg}",
        )
