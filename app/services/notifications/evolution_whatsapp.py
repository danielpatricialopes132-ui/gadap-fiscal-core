"""Cliente HTTP oficial para envio de mensagens e documentos via Evolution API (WhatsApp).

Integrado com a instância corporativa da Evolution API para envio de:
- Mensagens de texto amigáveis de notificação de autorização de NF-e, NFC-e e NFS-e.
- Documentos PDF (DANFE A4 / Bobina 80mm) a partir de URLs públicas ou assinadas do Supabase Storage.
"""

from typing import Optional, Dict, Any
import re
import logging
import requests

from app.core.config import settings

logger = logging.getLogger("gadap.whatsapp")


class EvolutionWhatsAppClient:
    """Cliente para despacho de notificações fiscais via WhatsApp com a Evolution API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        instance: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.EVOLUTION_API_URL).rstrip("/")
        self.api_key = api_key or settings.EVOLUTION_API_KEY
        self.instance = instance or settings.EVOLUTION_INSTANCE_NAME
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    @classmethod
    def sanitizar_numero(cls, telefone: str) -> str:
        """Formata o número de telefone brasileiro garantindo DDI 55 + DDD + dígitos numéricos.

        Exemplos de entrada:
        - "(11) 99999-8888" -> "5511999998888"
        - "11999998888" -> "5511999998888"
        - "5511999998888" -> "5511999998888"
        """
        digitos = re.sub(r"\D", "", telefone or "")
        if not digitos:
            raise ValueError("Número de telefone não pode ser vazio.")

        # Se já possui o código do Brasil 55
        if len(digitos) in (12, 13) and digitos.startswith("55"):
            return digitos

        # Se informado apenas DDD + Número (10 ou 11 dígitos)
        if len(digitos) in (10, 11):
            return f"55{digitos}"

        return digitos

    def enviar_mensagem_texto(self, telefone: str, texto: str) -> Dict[str, Any]:
        """Dispara uma mensagem de texto simples.

        Endpoint: POST {base_url}/message/sendText/{instance}
        Compatível com Evolution API v1.x e v2.x (versão instalada: 2.3.7).
        """
        numero_formatado = self.sanitizar_numero(telefone)
        url = f"{self.base_url}/message/sendText/{self.instance}"
        payload = {
            "number": numero_formatado,
            "text": texto,
            "delay": 1200,
        }

        try:
            logger.info(f"Disparando WhatsApp texto para {numero_formatado}...")
            resp = requests.post(url, headers=self.headers, json=payload, timeout=25)
            data = resp.json() if resp.text else {}
            if resp.status_code in (200, 201):
                msg_id = (
                    data.get("key", {}).get("id")
                    or data.get("id")
                    or data.get("messageId")
                )
                logger.info(f"WhatsApp texto enviado com sucesso! Message ID: {msg_id}")
                return {
                    "sucesso": True,
                    "status_code": resp.status_code,
                    "message_id": msg_id,
                    "data": data,
                }
            logger.warning(f"Evolution API retornou status {resp.status_code}: {resp.text}")
            return {"sucesso": False, "status_code": resp.status_code, "erro": resp.text}
        except Exception as e:
            logger.error(f"Falha de conexão com Evolution API sendText: {e}")
            return {"sucesso": False, "erro": str(e)}

    def enviar_documento_pdf(
        self,
        telefone: str,
        pdf_url: str,
        nome_arquivo: str = "DANFE.pdf",
        legenda: str = "",
    ) -> Dict[str, Any]:
        """Dispara um documento PDF através do endpoint sendMedia.

        Endpoint: POST {base_url}/message/sendMedia/{instance}
        Compatível com Evolution API v2.3.7.
        """
        numero_formatado = self.sanitizar_numero(telefone)
        url = f"{self.base_url}/message/sendMedia/{self.instance}"
        payload = {
            "number": numero_formatado,
            "mediatype": "document",
            "media": pdf_url,
            "fileName": nome_arquivo,
            "caption": legenda,
            "delay": 1200,
        }

        try:
            logger.info(f"Enviando PDF via WhatsApp para {numero_formatado}: {pdf_url}")
            resp = requests.post(url, headers=self.headers, json=payload, timeout=35)
            data = resp.json() if resp.text else {}
            if resp.status_code in (200, 201):
                msg_id = (
                    data.get("key", {}).get("id")
                    or data.get("id")
                    or data.get("messageId")
                )
                logger.info(f"DANFE PDF enviado com sucesso! Message ID: {msg_id}")
                return {
                    "sucesso": True,
                    "status_code": resp.status_code,
                    "message_id": msg_id,
                    "data": data,
                }
            logger.warning(f"Evolution API sendMedia retornou {resp.status_code}: {resp.text}")
            return {"sucesso": False, "status_code": resp.status_code, "erro": resp.text}
        except Exception as e:
            logger.error(f"Falha ao enviar documento PDF via Evolution API: {e}")
            return {"sucesso": False, "erro": str(e)}

    def enviar_notificacao_nota_autorizada(
        self,
        chave_acesso: str,
        numero_nota: int,
        destinatario_nome: str,
        telefone: str,
        pdf_url: str,
        qr_code_url: Optional[str] = None,
        razao_social_emitente: str = "GADAP Fiscal Hub",
    ) -> Dict[str, Any]:
        """Dispara a notificação de nota fiscal autorizada com mensagem personalizada e DANFE anexo."""
        mensagem = (
            f"🧾 *Olá, {destinatario_nome}!* 🧾\n\n"
            f"Seu documento fiscal foi emitido com sucesso por *{razao_social_emitente}*.\n\n"
            f"📋 *Dados do Documento:*\n"
            f"• *Número da Nota:* {numero_nota}\n"
            f"• *Chave de Acesso:* \n`{chave_acesso}`\n"
        )
        if qr_code_url:
            mensagem += f"\n🔍 *Consultar NFC-e:* {qr_code_url}\n"

        mensagem += "\n📎 Segue em anexo o arquivo oficial do *DANFE em PDF* para sua conferência e arquivo."

        nome_pdf = f"DANFE_NFe_{numero_nota}_{chave_acesso[:8]}.pdf"
        return self.enviar_documento_pdf(
            telefone=telefone,
            pdf_url=pdf_url,
            nome_arquivo=nome_pdf,
            legenda=mensagem,
        )
