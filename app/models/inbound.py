"""Modelos de Banco de Dados relacionais para Inbound DF-e (Documentos Recebidos de Fornecedores).

Tabelas:
- notas_recebidas: armazena documentos e resumos capturados via NFeDistribuicaoDFe.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class NotaRecebida(Base):
    """Documentos Fiscais emitidos contra o CNPJ da empresa (Inbound DF-e)."""
    __tablename__ = "notas_recebidas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    empresa_id = Column(String(36), ForeignKey("empresas.id"), nullable=False, index=True)
    chave_acesso = Column(String(50), unique=True, index=True, nullable=False)
    cnpj_emitente = Column(String(14), nullable=False, index=True)
    nome_emitente = Column(String(120), nullable=True)
    valor_total = Column(Numeric(15, 2), nullable=False, default=0.00)
    data_emissao = Column(DateTime(timezone=True), nullable=True)
    nsu = Column(String(20), nullable=False, index=True)
    
    # Status da Manifestação: SEM_MANIFESTACAO, CIENCIA, CONFIRMADA, DESCONHECIDA, NAO_REALIZADA
    status_manifestacao = Column(String(30), default="SEM_MANIFESTACAO", index=True, nullable=False)
    protocolo_manifestacao = Column(String(50), nullable=True)
    data_manifestacao = Column(DateTime(timezone=True), nullable=True)
    
    # Tipo de conteúdo: RESUMO (resNFe) ou COMPLETO (procNFe)
    tipo_conteudo = Column(String(20), default="RESUMO", nullable=False)
    xml_completo_path = Column(Text, nullable=True)
    storage_url = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    empresa = relationship("Empresa", backref="notas_recebidas")

    __table_args__ = (
        Index("idx_nota_rec_empresa_nsu", "empresa_id", "nsu"),
        Index("idx_nota_rec_status_manifestacao", "status_manifestacao"),
    )
