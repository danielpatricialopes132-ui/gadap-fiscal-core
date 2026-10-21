"""Camada unificada de persistência e Storage de documentos fiscais eletrônicos.

Armazena os arquivos definitivos:
- XMLs (<nfeProc>, <procEventoNFe>, <procInutNFe>, <NFSe>)
- DANFEs / DAMDFEs em PDF
- Histórico em banco relacional (Supabase / PostgreSQL) ou em storage local / Supabase Storage.
"""

from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timezone
import base64
import json
import requests

from app.core.config import settings


class FiscalStorageService:
    """Gerencia o salvamento local e sincronização com Supabase Storage / Database."""

    def __init__(self, base_dir: str = "storage"):
        self.base_dir = Path(base_dir)
        self.xml_dir = self.base_dir / "xml"
        self.pdf_dir = self.base_dir / "pdf"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Cria as pastas locais caso não existam."""
        self.xml_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)

    def salvar_xml_local(self, chave_ou_id: str, xml_conteudo: str, subpasta: str = "autorizadas") -> str:
        """Salva o XML localmente em disco e retorna o path absoluto."""
        pasta_destino = self.xml_dir / subpasta
        pasta_destino.mkdir(parents=True, exist_ok=True)
        arquivo_path = pasta_destino / f"{chave_ou_id}.xml"
        with open(arquivo_path, "w", encoding="utf-8") as f:
            f.write(xml_conteudo)
        return str(arquivo_path)

    def salvar_pdf_local(self, chave_ou_id: str, pdf_bytes: bytes, subpasta: str = "danfe") -> str:
        """Salva o DANFE PDF em disco e retorna o path absoluto."""
        pasta_destino = self.pdf_dir / subpasta
        pasta_destino.mkdir(parents=True, exist_ok=True)
        arquivo_path = pasta_destino / f"{chave_ou_id}.pdf"
        with open(arquivo_path, "wb") as f:
            f.write(pdf_bytes)
        return str(arquivo_path)

    def upload_supabase_storage(
        self,
        bucket_name: str,
        file_path: str,
        content_bytes: bytes,
        content_type: str = "application/xml",
    ) -> Optional[str]:
        """Faz upload de arquivo para o Supabase Storage via REST API."""
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            return None

        url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{bucket_name}/{file_path}"
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
            "apikey": settings.SUPABASE_KEY,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        try:
            resp = requests.post(url, headers=headers, data=content_bytes, timeout=15)
            if resp.status_code in (200, 201):
                return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{bucket_name}/{file_path}"
        except Exception:
            pass
        return None

    def registrar_documento(
        self,
        tipo_documento: str,
        chave_acesso: str,
        numero: int,
        serie: int,
        emitente_cnpj: str,
        destinatario_doc: Optional[str],
        valor_total: float,
        status: str,
        xml_conteudo: str,
        pdf_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Orquestra o arquivamento do XML e PDF local e sincronização com Supabase."""
        caminho_xml = self.salvar_xml_local(chave_ou_id=chave_acesso, xml_conteudo=xml_conteudo)
        caminho_pdf = None
        if pdf_bytes:
            caminho_pdf = self.salvar_pdf_local(chave_ou_id=chave_acesso, pdf_bytes=pdf_bytes)

        # Upload para Supabase Storage se configurado
        url_xml_remoto = None
        url_pdf_remoto = None
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            url_xml_remoto = self.upload_supabase_storage(
                bucket_name="fiscal-documents",
                file_path=f"xml/{chave_acesso}.xml",
                content_bytes=xml_conteudo.encode("utf-8"),
                content_type="application/xml",
            )
            if pdf_bytes:
                url_pdf_remoto = self.upload_supabase_storage(
                    bucket_name="fiscal-documents",
                    file_path=f"pdf/{chave_acesso}.pdf",
                    content_bytes=pdf_bytes,
                    content_type="application/pdf",
                )

        return {
            "chave_acesso": chave_acesso,
            "tipo_documento": tipo_documento,
            "status": status,
            "caminho_xml_local": caminho_xml,
            "caminho_pdf_local": caminho_pdf,
            "url_xml_remoto": url_xml_remoto,
            "url_pdf_remoto": url_pdf_remoto,
            "data_registro": datetime.now(timezone.utc).isoformat(),
        }
