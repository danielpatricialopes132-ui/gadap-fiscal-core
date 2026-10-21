"""Cliente de Armazenamento de Arquivos Fiscais no Supabase Storage.

Gerencia o bucket privado 'documentos-fiscais', upload de XMLs definitivos (<procNFe>),
DANFEs em PDF e geração de URLs assinadas temporárias para o painel web.
"""

from typing import Optional
from pathlib import Path
import requests

from app.core.config import settings
from app.db.session import get_supabase_client


class SupabaseStorageService:
    """Serviço de gerenciamento do Supabase Storage para arquivos fiscais."""

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or settings.SUPABASE_STORAGE_BUCKET
        self.client = get_supabase_client()
        self.base_url = (settings.SUPABASE_URL or "").rstrip("/")
        self.api_key = settings.SUPABASE_KEY or ""

    def ensure_bucket_exists(self) -> bool:
        """Verifica se o bucket existe ou tenta criá-lo como privado."""
        if not self.base_url or not self.api_key:
            return False

        url = f"{self.base_url}/storage/v1/bucket"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }
        try:
            # Lista buckets
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                buckets = res.json()
                if any(b.get("id") == self.bucket_name or b.get("name") == self.bucket_name for b in buckets):
                    return True

            # Cria se não existir
            create_payload = {
                "id": self.bucket_name,
                "name": self.bucket_name,
                "public": False,
                "file_size_limit": 10485760,  # 10MB
                "allowed_mime_types": ["application/xml", "text/xml", "application/pdf", "application/zip"],
            }
            res_create = requests.post(url, headers=headers, json=create_payload, timeout=10)
            return res_create.status_code in (200, 201)
        except Exception:
            return False

    def upload_bytes(self, path: str, content: bytes, content_type: str = "application/xml") -> str:
        """Envia bytes para o Supabase Storage e retorna o bucket_path."""
        if not self.base_url or not self.api_key:
            # Fallback em disco local caso Supabase não esteja acessível
            local_fallback = Path("storage") / self.bucket_name / path
            local_fallback.parent.mkdir(parents=True, exist_ok=True)
            with open(local_fallback, "wb") as f:
                f.write(content)
            return f"local://{path}"

        clean_path = path.lstrip("/")
        url = f"{self.base_url}/storage/v1/object/{self.bucket_name}/{clean_path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "apikey": self.api_key,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        try:
            res = requests.post(url, headers=headers, data=content, timeout=20)
            if res.status_code in (200, 201):
                return clean_path
        except Exception:
            pass

        # Fallback local em caso de erro na rede
        local_fallback = Path("storage") / self.bucket_name / path
        local_fallback.parent.mkdir(parents=True, exist_ok=True)
        with open(local_fallback, "wb") as f:
            f.write(content)
        return f"local://{path}"

    def salvar_xml_autorizado(self, chave_acesso: str, xml_conteudo: str) -> str:
        """Faz upload do arquivo definitivo procNFe-{chave}.xml."""
        path = f"xml/procNFe-{chave_acesso}.xml"
        return self.upload_bytes(path=path, content=xml_conteudo.encode("utf-8"), content_type="application/xml")

    def salvar_danfe_pdf(self, chave_acesso: str, pdf_bytes: bytes) -> str:
        """Faz upload do PDF do DANFE danfe-{chave}.pdf."""
        path = f"pdf/danfe-{chave_acesso}.pdf"
        return self.upload_bytes(path=path, content=pdf_bytes, content_type="application/pdf")

    def obter_url_download_temporaria(self, bucket_path: str, expires_in: int = 3600) -> str:
        """Gera URL assinada temporária para download seguro a partir do frontend."""
        if bucket_path.startswith("local://") or not self.base_url or not self.api_key:
            return f"{settings.NEXT_PUBLIC_API_URL or ''}/api/v1/fiscal/documentos/{bucket_path.split('/')[-1]}/download"

        clean_path = bucket_path.lstrip("/")
        url = f"{self.base_url}/storage/v1/object/sign/{self.bucket_name}/{clean_path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"expiresIn": expires_in}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code in (200, 201):
                signed_url = res.json().get("signedURL", "")
                if signed_url:
                    return f"{self.base_url}/storage/v1{signed_url}"
        except Exception:
            pass
        return f"{self.base_url}/storage/v1/object/public/{self.bucket_name}/{clean_path}"
