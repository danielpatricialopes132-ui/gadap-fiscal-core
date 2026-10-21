"""Script de Teste de Disparo Real via Evolution API para o WhatsApp informado.

Destinatário: 5511913192703
Instância: ecostone
Provedor: Evolution API
"""

import sys
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import settings
from app.services.notifications.evolution_whatsapp import EvolutionWhatsAppClient


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("teste_disparo_whatsapp")

TELEFONE_DESTINO = "5511913192703"


def executar_teste_disparo():
    print("=" * 70)
    print(" GADAP FISCAL CORE - DISPARO DE TESTE WHATSAPP (EVOLUTION API)")
    print("=" * 70)
    print(f"Base URL:   {settings.EVOLUTION_API_URL}")
    print(f"Instância:  {settings.EVOLUTION_INSTANCE_NAME}")
    print(f"Destino:    {TELEFONE_DESTINO}")
    print("=" * 70)

    client = EvolutionWhatsAppClient()

    # 1. Teste de Sanitização
    numero_sanitizado = client.sanitizar_numero(TELEFONE_DESTINO)
    print(f"\n[1/3] Número sanitizado com sucesso: {numero_sanitizado}")

    # 2. Teste de Mensagem de Texto
    print(f"\n[2/3] Enviando mensagem de texto de validação...")
    texto_teste = (
        "🟢 *GADAP Fiscal Core - Teste de Conexão WhatsApp*\n\n"
        "Olá! Este é um teste automático de integração com a *Evolution API*.\n"
        "O canal de mensageria fiscal está pronto para enviar DANFEs e notificações de autorização da SEFAZ!"
    )
    res_texto = client.enviar_mensagem_texto(telefone=numero_sanitizado, texto=texto_teste)
    print(f"Resultado Envio Texto: {res_texto}")

    # 3. Teste de Notificação de Nota Fiscal Autorizada com PDF
    print(f"\n[3/3] Enviando notificação simulada de Nota Autorizada com DANFE...")
    # PDF de exemplo / DANFE
    pdf_teste_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    chave_simulada = "35240212345678000195550010000001231000001234"
    
    res_danfe = client.enviar_notificacao_nota_autorizada(
        chave_acesso=chave_simulada,
        numero_nota=1052,
        destinatario_nome="Administrador Ecostone",
        telefone=numero_sanitizado,
        pdf_url=pdf_teste_url,
        razao_social_emitente="ECOSTONE COMERCIO DE ROCHAS LTDA",
    )
    print(f"Resultado Envio Notificação + PDF: {res_danfe}")
    print("=" * 70)


if __name__ == "__main__":
    executar_teste_disparo()
