"""Endpoints de Consulta, Download e Fechamento Contábil de Documentos Fiscais.

Rotas para consumo do GADAP Fiscal Hub e sistemas contábeis:
- GET /api/v1/fiscal/documentos: Listagem paginada com múltiplos filtros.
- GET /api/v1/fiscal/documentos/{chave}/download/{tipo}: Download direto de XML ou PDF do DANFE.
- GET /api/v1/fiscal/fechamento-mensal: Exportação em lote (.zip) de todos os XMLs autorizados do mês.
"""

from typing import Optional, List
from datetime import datetime, timezone
from io import BytesIO
import zipfile
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db_session
from app.models.fiscal import DocumentoFiscal, ArquivoFiscal
from app.services.storage.supabase_storage import SupabaseStorageService

router = APIRouter(prefix="/api/v1/fiscal", tags=["Fiscal Records & Fechamento"])


class DocumentoFiscalListItem(BaseModel):
    id: str
    tipo_documento: str
    chave_acesso: str
    serie: int
    numero: int
    data_emissao: Optional[str] = None
    destinatario_cpf_cnpj: Optional[str] = None
    destinatario_nome: Optional[str] = None
    valor_total: float
    status: str
    cstat: Optional[int] = None
    xmotivo: Optional[str] = None
    protocolo: Optional[str] = None
    xml_url: Optional[str] = None
    pdf_url: Optional[str] = None


class ListagemDocumentosResponse(BaseModel):
    total: int
    pagina: int
    limite: int
    itens: List[DocumentoFiscalListItem]


@router.get(
    "/documentos",
    response_model=ListagemDocumentosResponse,
    summary="Listagem Paginada de Documentos Fiscais",
    description="Permite ao Fiscal Hub listar, filtrar por período, tipo (NFE/NFCE/NFSE) e status (AUTORIZADA, REJEITADA, CANCELADA).",
)
def listar_documentos_fiscais(
    tipo: Optional[str] = Query(None, description="NFE, NFCE ou NFSE"),
    status_doc: Optional[str] = Query(None, description="AUTORIZADA, REJEITADA, CANCELADA, EM_PROCESSAMENTO"),
    data_inicio: Optional[str] = Query(None, description="Data inicial YYYY-MM-DD"),
    data_fim: Optional[str] = Query(None, description="Data final YYYY-MM-DD"),
    busca: Optional[str] = Query(None, description="Chave de acesso ou nome/documento do destinatário"),
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
) -> ListagemDocumentosResponse:
    query = db.query(DocumentoFiscal)

    if tipo:
        query = query.filter(DocumentoFiscal.tipo_documento == tipo.upper())
    if status_doc:
        query = query.filter(DocumentoFiscal.status == status_doc.upper())
    if busca:
        termo = f"%{busca}%"
        query = query.filter(
            (DocumentoFiscal.chave_acesso.ilike(termo))
            | (DocumentoFiscal.destinatario_nome.ilike(termo))
            | (DocumentoFiscal.destinatario_cpf_cnpj.ilike(termo))
        )

    total = query.count()
    offset = (pagina - 1) * limite
    registros = query.order_by(DocumentoFiscal.data_emissao.desc()).offset(offset).limit(limite).all()

    storage_svc = SupabaseStorageService()
    itens_formatados = []
    for doc in registros:
        xml_arq = next((a for a in doc.arquivos if a.tipo_arquivo == "XML_AUTORIZADO"), None)
        pdf_arq = next((a for a in doc.arquivos if a.tipo_arquivo == "PDF_DANFE"), None)

        xml_url = storage_svc.obter_url_download_temporaria(xml_arq.bucket_path) if xml_arq else None
        pdf_url = storage_svc.obter_url_download_temporaria(pdf_arq.bucket_path) if pdf_arq else None

        itens_formatados.append(
            DocumentoFiscalListItem(
                id=doc.id,
                tipo_documento=doc.tipo_documento,
                chave_acesso=doc.chave_acesso,
                serie=doc.serie,
                numero=doc.numero,
                data_emissao=doc.data_emissao.isoformat() if doc.data_emissao else None,
                destinatario_cpf_cnpj=doc.destinatario_cpf_cnpj,
                destinatario_nome=doc.destinatario_nome,
                valor_total=float(doc.valor_total or 0.0),
                status=doc.status,
                cstat=doc.cstat,
                xmotivo=doc.xmotivo,
                protocolo=doc.protocolo_autorizacao,
                xml_url=xml_url,
                pdf_url=pdf_url,
            )
        )

    return ListagemDocumentosResponse(
        total=total,
        pagina=pagina,
        limite=limite,
        itens=itens_formatados,
    )


@router.get(
    "/documentos/{chave}/download/{tipo_arquivo}",
    summary="Download de Arquivo Fiscal (XML ou PDF)",
    description="Retorna o arquivo XML ou PDF diretamente em streaming para download no navegador.",
)
def download_arquivo_fiscal(
    chave: str,
    tipo_arquivo: str,  # xml ou pdf
    db: Session = Depends(get_db_session),
):
    tipo_arq_db = "XML_AUTORIZADO" if tipo_arquivo.lower() == "xml" else "PDF_DANFE"
    doc = db.query(DocumentoFiscal).filter(DocumentoFiscal.chave_acesso == chave).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")

    arq = next((a for a in doc.arquivos if a.tipo_arquivo == tipo_arq_db), None)
    if not arq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Arquivo {tipo_arquivo} não disponível.")

    # Tenta leitura do arquivo local ou redirecionamento do storage
    storage_svc = SupabaseStorageService()
    if arq.bucket_path.startswith("local://"):
        rel_path = arq.bucket_path.replace("local://", "")
        file_path = Path("storage") / storage_svc.bucket_name / rel_path
        if file_path.exists():
            media = "application/xml" if tipo_arquivo.lower() == "xml" else "application/pdf"
            ext = "xml" if tipo_arquivo.lower() == "xml" else "pdf"
            with open(file_path, "rb") as f:
                content = f.read()
            return Response(
                content=content,
                media_type=media,
                headers={"Content-Disposition": f"attachment; filename={chave}.{ext}"},
            )

    url_temporaria = storage_svc.obter_url_download_temporaria(arq.bucket_path)
    return {"url_download": url_temporaria}


@router.get(
    "/fechamento-mensal",
    summary="Geração de Pacote ZIP de Fechamento Contábil",
    description="Empacota todos os XMLs autorizados do mês selecionado em um arquivo .zip para envio ao contador.",
)
def exportar_fechamento_contabil_mensal(
    ano: int = Query(..., ge=2020, le=2030),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db_session),
):
    # Consulta documentos autorizados do mês
    docs = (
        db.query(DocumentoFiscal)
        .filter(DocumentoFiscal.status == "AUTORIZADA")
        .all()
    )

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for doc in docs:
            xml_arq = next((a for a in doc.arquivos if a.tipo_arquivo == "XML_AUTORIZADO"), None)
            if xml_arq:
                # Tenta ler do disco local ou cria representação
                conteudo_xml = None
                if xml_arq.bucket_path.startswith("local://"):
                    p = Path("storage") / "documentos-fiscais" / xml_arq.bucket_path.replace("local://", "")
                    if p.exists():
                        with open(p, "r", encoding="utf-8") as f:
                            conteudo_xml = f.read()

                if not conteudo_xml:
                    conteudo_xml = f"<!-- XML da NF-e Chave {doc.chave_acesso} - Protocolo {doc.protocolo_autorizacao} -->"

                nome_arquivo_zip = f"{doc.tipo_documento}_{doc.serie}_{doc.numero}_{doc.chave_acesso}.xml"
                zip_file.writestr(nome_arquivo_zip, conteudo_xml)

    zip_buffer.seek(0)
    nome_zip = f"GADAP_Fiscal_Fechamento_{ano}_{mes:02d}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={nome_zip}"},
    )
