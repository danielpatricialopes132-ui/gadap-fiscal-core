"""Modelos de Banco de Dados relacionais para o ciclo de vida fiscal e auditoria.

Tabelas:
- empresas
- documentos_fiscais
- arquivos_fiscais
- eventos_fiscais
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class Empresa(Base):
    """Cadastro de empresas emitentes (Simples Nacional CRT=1)."""
    __tablename__ = "empresas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cnpj = Column(String(14), unique=True, nullable=False, index=True)
    razao_social = Column(String(120), nullable=False)
    inscricao_estadual = Column(String(20), nullable=False)
    crt = Column(Integer, default=1, nullable=False)
    uf = Column(String(2), nullable=False)
    ambiente_padrao = Column(String(20), default="homologacao")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    documentos = relationship("DocumentoFiscal", back_populates="empresa", cascade="all, delete-orphan")


class DocumentoFiscal(Base):
    """Registro unificado do ciclo de vida de NF-e, NFC-e e NFS-e."""
    __tablename__ = "documentos_fiscais"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    empresa_id = Column(String(36), ForeignKey("empresas.id"), nullable=True, index=True)
    idempotency_key = Column(String(64), unique=True, index=True, nullable=True)
    tipo_documento = Column(String(10), nullable=False)  # NFE, NFCE, NFSE
    chave_acesso = Column(String(50), unique=True, index=True, nullable=False)
    serie = Column(Integer, nullable=False)
    numero = Column(Integer, nullable=False)
    data_emissao = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    destinatario_cpf_cnpj = Column(String(14), nullable=True, index=True)
    destinatario_nome = Column(String(120), nullable=True)
    valor_total = Column(Numeric(15, 2), nullable=False, default=0.00)
    
    # Status: EM_PROCESSAMENTO, AUTORIZADA, REJEITADA, CANCELADA
    status = Column(String(20), default="EM_PROCESSAMENTO", index=True, nullable=False)
    cstat = Column(Integer, nullable=True)
    xmotivo = Column(Text, nullable=True)
    protocolo_autorizacao = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", back_populates="documentos")
    arquivos = relationship("ArquivoFiscal", back_populates="documento", cascade="all, delete-orphan")
    eventos = relationship("EventoFiscal", back_populates="documento", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_doc_tipo_status", "tipo_documento", "status"),
        Index("idx_doc_data_emissao", "data_emissao"),
    )


class ArquivoFiscal(Base):
    """Localização e referências no Supabase Storage dos XMLs e PDFs gerados."""
    __tablename__ = "arquivos_fiscais"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    documento_id = Column(String(36), ForeignKey("documentos_fiscais.id"), nullable=False, index=True)
    tipo_arquivo = Column(String(30), nullable=False)  # XML_AUTORIZADO, PDF_DANFE, XML_EVENTO
    bucket_path = Column(Text, nullable=False)
    storage_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    documento = relationship("DocumentoFiscal", back_populates="arquivos")


class EventoFiscal(Base):
    """Histórico de eventos fiscais (Cancelamento, CC-e, Manifestação)."""
    __tablename__ = "eventos_fiscais"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    documento_id = Column(String(36), ForeignKey("documentos_fiscais.id"), nullable=False, index=True)
    tipo_evento = Column(String(30), nullable=False)  # CANCELAMENTO, CARTA_CORRECAO, MANIFESTACAO
    seq_evento = Column(Integer, default=1, nullable=False)
    protocolo = Column(String(50), nullable=True)
    xml_evento_path = Column(Text, nullable=True)
    justificativa = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    documento = relationship("DocumentoFiscal", back_populates="eventos")
