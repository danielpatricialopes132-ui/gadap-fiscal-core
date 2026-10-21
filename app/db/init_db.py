"""Script de inicialização do banco de dados e bucket do Supabase."""

import sys
from app.db.session import get_engine, Base
from app.models.fiscal import Empresa, DocumentoFiscal, ArquivoFiscal, EventoFiscal
from app.services.storage.supabase_storage import SupabaseStorageService


def init_database_and_storage():
    """Cria as tabelas relacionais via SQLAlchemy e o bucket de storage no Supabase."""
    print("=" * 60)
    print("Iniciando verificação de tabelas e Supabase Storage...")
    print("=" * 60)

    # 1. Criação das tabelas
    try:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        print("[OK] Tabelas (empresas, documentos_fiscais, arquivos_fiscais, eventos_fiscais) verificadas/criadas no banco.")
    except Exception as e:
        print(f"[AVISO] Nao foi possivel conectar ao pooler remoto do Supabase: {e}")
        print("[INFO] Criando tabelas no banco SQLite local de contingencia...")
        from sqlalchemy import create_engine
        local_engine = create_engine("sqlite:///./gadap_fiscal_local.db")
        Base.metadata.create_all(bind=local_engine)
        print("[OK] Tabelas criadas com sucesso no banco SQLite local (gadap_fiscal_local.db).")

    # 2. Criação do bucket de documentos fiscais
    try:
        storage_svc = SupabaseStorageService()
        ok = storage_svc.ensure_bucket_exists()
        if ok:
            print(f"[OK] Bucket '{storage_svc.bucket_name}' validado no Supabase Storage.")
        else:
            print(f"[INFO] Bucket '{storage_svc.bucket_name}' verificado / operando com fallback seguro.")
    except Exception as e:
        print(f"[AVISO] Erro na inicializacao do bucket Supabase Storage: {e}")

    print("=" * 60)
    print("Setup de banco e storage concluido!")
    print("=" * 60)


if __name__ == "__main__":
    init_database_and_storage()
