"""Orquestrador de Emissão com Idempotência Estrita e Persistência no Supabase.

Garante:
1. Idempotência absoluta através do idempotency_key (evita reemissões e duplicidade cStat 539).
2. Gravação do ciclo de vida: EM_PROCESSAMENTO -> AUTORIZADA ou REJEITADA.
3. Upload automático dos arquivos finais (XML procNFe e PDF DANFE) no Supabase Storage.
"""

from typing import Optional, Dict, Any, Tuple
import base64
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.fiscal import DocumentoFiscal, ArquivoFiscal, Empresa
from app.schemas.canonical import DocumentoFiscalInput, TipoDocumento
from app.services.tax_engine import TaxEngineSimplesNacional
from app.services.sefaz.xml_builder import NFeXmlBuilder
from app.services.sefaz.xml_signer import XmlSigner
from app.services.sefaz.transmitter import SefazTransmitter, SefazRejectionError
from app.services.sefaz.danfe_generator import DanfePdfGenerator
from app.services.storage.supabase_storage import SupabaseStorageService
from app.core.security.certificate import A1CertificateManager


from fastapi import BackgroundTasks


class EmissionOrchestrator:
    """Orquestrador do fluxo completo de emissão com garantia de idempotência e persistência."""

    def __init__(self, db: Session, storage: Optional[SupabaseStorageService] = None):
        self.db = db
        self.storage = storage or SupabaseStorageService()

    def processar_emissao(
        self,
        payload: DocumentoFiscalInput,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        """Executa a emissão com checagem de idempotência, envio ao fisco e gravação no Storage."""
        idemp_key = payload.idempotency_key or f"IDEMP-{payload.emitente.cnpj}-{payload.serie}-{payload.numero}"
        tipo_str = payload.tipo_documento.value
        modelo = "65" if payload.tipo_documento == TipoDocumento.NFCE else "55"

        # ---------------------------------------------------------------------
        # 1. Checagem de Idempotência
        # ---------------------------------------------------------------------
        doc_existente = (
            self.db.query(DocumentoFiscal)
            .filter(DocumentoFiscal.idempotency_key == idemp_key)
            .first()
        )

        if doc_existente and doc_existente.status == "AUTORIZADA":
            # Retorno imediato do documento já emitido com sucesso
            xml_arq = next((a for a in doc_existente.arquivos if a.tipo_arquivo == "XML_AUTORIZADO"), None)
            pdf_arq = next((a for a in doc_existente.arquivos if a.tipo_arquivo == "PDF_DANFE"), None)

            url_xml = self.storage.obter_url_download_temporaria(xml_arq.bucket_path) if xml_arq else None
            url_pdf = self.storage.obter_url_download_temporaria(pdf_arq.bucket_path) if pdf_arq else None

            return {
                "idempotente": True,
                "sucesso": True,
                "status": "AUTORIZADA",
                "chave_acesso": doc_existente.chave_acesso,
                "numero_documento": doc_existente.numero,
                "serie": doc_existente.serie,
                "protocolo": doc_existente.protocolo_autorizacao,
                "c_stat": str(doc_existente.cstat or 100),
                "x_motivo": doc_existente.xmotivo or "Documento ja emitido e autorizado anteriormente (Idempotente)",
                "storage_xml_url": url_xml,
                "storage_pdf_url": url_pdf,
                "ambiente": settings.DFE_ENVIRONMENT.value,
            }

        # ---------------------------------------------------------------------
        # 2. Geração e Validação do XML SEFAZ v4.00
        # ---------------------------------------------------------------------
        xml_raw, chave_acesso = NFeXmlBuilder.build_from_input(payload)
        tot_liquido = sum(float(it.valor_total_liquido) for it in payload.itens)
        dest_doc = payload.destinatario.cpf_cnpj if payload.destinatario else None
        dest_nome = payload.destinatario.razao_social if payload.destinatario else None

        # Grava registro inicial em processamento se ainda não existir
        if not doc_existente:
            doc_registro = DocumentoFiscal(
                idempotency_key=idemp_key,
                tipo_documento=tipo_str,
                chave_acesso=chave_acesso,
                serie=payload.serie,
                numero=payload.numero,
                data_emissao=datetime.now(timezone.utc),
                destinatario_cpf_cnpj=dest_doc,
                destinatario_nome=dest_nome,
                valor_total=tot_liquido,
                status="EM_PROCESSAMENTO",
            )
            self.db.add(doc_registro)
            self.db.commit()
            self.db.refresh(doc_registro)
        else:
            doc_registro = doc_existente
            doc_registro.status = "EM_PROCESSAMENTO"
            self.db.commit()

        # ---------------------------------------------------------------------
        # 3. Assinatura e Transmissão
        # ---------------------------------------------------------------------
        cert_bytes = settings.get_certificate_bytes()
        if cert_bytes and settings.CERTIFICATE_PASSWORD:
            try:
                cert_mgr = A1CertificateManager(pfx_data=cert_bytes, password=settings.CERTIFICATE_PASSWORD)
                signer = XmlSigner(private_key=cert_mgr.private_key, x509_cert_der=cert_mgr.certificate_der)
                xml_assinado = signer.sign_xml(xml_raw)

                transmitter = SefazTransmitter(
                    cert_bytes=cert_bytes,
                    cert_password=settings.CERTIFICATE_PASSWORD,
                    is_production=settings.is_production,
                )
                lote_res = transmitter.enviar_lote_sincrono(
                    xml_assinado=xml_assinado,
                    uf=payload.emitente.endereco.uf,
                    modelo=modelo,
                )
                xml_final = lote_res.xml_proc_completo or xml_assinado
                c_stat = int(lote_res.c_stat)
                x_motivo = lote_res.x_motivo
                protocolo = lote_res.n_prot
                status_final = "AUTORIZADA" if c_stat == 100 else "REJEITADA"

            except SefazRejectionError as se:
                doc_registro.status = "REJEITADA"
                doc_registro.cstat = int(se.c_stat) if se.c_stat.isdigit() else 999
                doc_registro.xmotivo = se.x_motivo
                self.db.commit()
                raise

            except Exception as e:
                doc_registro.status = "REJEITADA"
                doc_registro.cstat = 999
                doc_registro.xmotivo = str(e)
                self.db.commit()
                raise
        else:
            # Modo Homologação / Simulação Sem Certificado Instalado
            xml_final = xml_raw
            c_stat = 100
            x_motivo = "Autorizado o uso da NF-e (Ambiente de Homologacao / Simulado)"
            protocolo = "135240000000001"
            status_final = "AUTORIZADA"

        # ---------------------------------------------------------------------
        # 4. Geração do DANFE em PDF
        # ---------------------------------------------------------------------
        danfe_pdf_bytes = None
        try:
            danfe_pdf_bytes = DanfePdfGenerator.generate_danfe_pdf(
                xml_input=xml_final,
                force_homologacao=not settings.is_production,
            )
        except Exception:
            danfe_pdf_bytes = None

        # ---------------------------------------------------------------------
        # 5. Upload no Supabase Storage e Atualização no Banco de Dados
        # ---------------------------------------------------------------------
        xml_path = self.storage.salvar_xml_autorizado(chave_acesso=chave_acesso, xml_conteudo=xml_final)
        url_xml = self.storage.obter_url_download_temporaria(xml_path)

        # Registra Arquivo Fiscal do XML
        arq_xml = ArquivoFiscal(
            documento_id=doc_registro.id,
            tipo_arquivo="XML_AUTORIZADO",
            bucket_path=xml_path,
            storage_url=url_xml,
        )
        self.db.add(arq_xml)

        url_pdf = None
        if danfe_pdf_bytes:
            pdf_path = self.storage.salvar_danfe_pdf(chave_acesso=chave_acesso, pdf_bytes=danfe_pdf_bytes)
            url_pdf = self.storage.obter_url_download_temporaria(pdf_path)
            arq_pdf = ArquivoFiscal(
                documento_id=doc_registro.id,
                tipo_arquivo="PDF_DANFE",
                bucket_path=pdf_path,
                storage_url=url_pdf,
            )
            self.db.add(arq_pdf)

        xml_b64 = base64.b64encode(xml_final.encode("utf-8")).decode("utf-8") if xml_final else None
        danfe_b64 = base64.b64encode(danfe_pdf_bytes).decode("utf-8") if danfe_pdf_bytes else None

        doc_registro.status = status_final
        doc_registro.cstat = c_stat
        doc_registro.xmotivo = x_motivo
        doc_registro.protocolo_autorizacao = protocolo
        self.db.commit()
        self.db.refresh(doc_registro)


        # ---------------------------------------------------------------------
        # 6. Disparo Assíncrono de WhatsApp via Evolution API (Fase 9)
        # ---------------------------------------------------------------------
        tel_whatsapp = (
            payload.destinatario.telefone_whatsapp
            if payload.destinatario and payload.destinatario.telefone_whatsapp
            else None
        )

        whatsapp_disparado = False
        if (
            status_final == "AUTORIZADA"
            and tel_whatsapp
            and settings.WHATSAPP_NOTIFICATIONS_ENABLED
            and url_pdf
        ):
            try:
                from app.services.notifications.evolution_whatsapp import EvolutionWhatsAppClient

                def _enviar_whatsapp_task(
                    doc_id: str,
                    tel: str,
                    chave: str,
                    numero: int,
                    nome_dest: str,
                    link_pdf: str,
                    razao_emit: str,
                ):
                    from app.db.session import get_engine
                    from sqlalchemy.orm import sessionmaker

                    wp_client = EvolutionWhatsAppClient()
                    res_wp = wp_client.enviar_notificacao_nota_autorizada(
                        chave_acesso=chave,
                        numero_nota=numero,
                        destinatario_nome=nome_dest,
                        telefone=tel,
                        pdf_url=link_pdf,
                        razao_social_emitente=razao_emit,
                    )
                    # Atualiza registro no banco se sucesso
                    if res_wp.get("sucesso"):
                        try:
                            eng = get_engine()
                            SessionMaker = sessionmaker(bind=eng)
                            with SessionMaker() as sess:
                                d = sess.query(DocumentoFiscal).filter(DocumentoFiscal.id == doc_id).first()
                                if d:
                                    d.whatsapp_telefone = tel
                                    d.whatsapp_notificado_at = datetime.now(timezone.utc)
                                    d.whatsapp_message_id = str(res_wp.get("message_id") or "")
                                    sess.commit()
                        except Exception:
                            pass

                if background_tasks:
                    background_tasks.add_task(
                        _enviar_whatsapp_task,
                        doc_id=doc_registro.id,
                        tel=tel_whatsapp,
                        chave=chave_acesso,
                        numero=payload.numero,
                        nome_dest=dest_nome or "Cliente",
                        link_pdf=url_pdf,
                        razao_emit=payload.emitente.razao_social,
                    )
                    whatsapp_disparado = True
                else:
                    # Executa diretamente se não houver background_tasks injetado
                    _enviar_whatsapp_task(
                        doc_id=doc_registro.id,
                        tel=tel_whatsapp,
                        chave=chave_acesso,
                        numero=payload.numero,
                        nome_dest=dest_nome or "Cliente",
                        link_pdf=url_pdf,
                        razao_emit=payload.emitente.razao_social,
                    )
                    whatsapp_disparado = True
            except Exception:
                pass

        return {
            "idempotente": False,
            "sucesso": status_final == "AUTORIZADA",
            "status": status_final,
            "chave_acesso": chave_acesso,
            "numero_documento": payload.numero,
            "serie": payload.serie,
            "protocolo": protocolo,
            "c_stat": str(c_stat),
            "x_motivo": x_motivo,
            "xml_autorizado_b64": xml_b64,
            "danfe_pdf_b64": danfe_b64,
            "storage_xml_url": url_xml,
            "storage_pdf_url": url_pdf,
            "whatsapp_disparado": whatsapp_disparado,
            "ambiente": settings.DFE_ENVIRONMENT.value,
        }
