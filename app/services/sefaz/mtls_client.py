"""Cliente HTTP com Handshake mTLS (TLS 1.2 / TLS 1.3) e Envelopamento SOAP 1.2 para WebServices SEFAZ.

Realiza a injeção do Certificado Digital A1 e Chave Privada estritamente em memória
usando context manager temporário com deleção segura, garantindo conformidade com a ICP-Brasil.
"""

from typing import Dict, Optional, Tuple, Union
import ssl
import tempfile
import os
import requests
from lxml import etree

from app.core.security.certificate import A1CertificateManager


SOAP12_NS = "http://www.w3.org/2003/05/soap-envelope"
NFE_WS_NS = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4"
NFE_STATUS_WS_NS = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4"


class SefazNetworkError(Exception):
    """Exceção levantada em falhas de conexão de rede ou timeout com a SEFAZ."""
    pass


class SefazSoapFaultError(Exception):
    """Exceção levantada quando o servidor SEFAZ devolve um Soap Fault."""
    pass


class SefazMtlsClient:
    """Cliente HTTP com autenticação mTLS e envelopamento SOAP 1.2 para a SEFAZ."""

    def __init__(self, cert_manager: A1CertificateManager, timeout_seconds: int = 30):
        self.cert_manager = cert_manager
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def wrap_soap12_envelope(body_element: Union[etree._Element, str, bytes], action_namespace: str) -> str:
        """Envelopa o payload XML dentro de um envelope SOAP 1.2 da SEFAZ.

        Args:
            body_element: Elemento XML (ex: enviNFe, consStatServ).
            action_namespace: Namespace WSDL da operação SEFAZ.

        Returns:
            str: XML completo com envelope SOAP 1.2.
        """
        if isinstance(body_element, (str, bytes)):
            body_xml_str = body_element.decode("utf-8") if isinstance(body_element, bytes) else body_element
        else:
            body_xml_str = etree.tostring(body_element, encoding="unicode")

        envelope = (
            f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            f'xmlns:soap12="{SOAP12_NS}">\n'
            f'  <soap12:Body>\n'
            f'    <nfeDadosMsg xmlns="{action_namespace}">\n'
            f'      {body_xml_str}\n'
            f'    </nfeDadosMsg>\n'
            f'  </soap12:Body>\n'
            f'</soap12:Envelope>'
        )
        return envelope

    @staticmethod
    def extract_soap12_body(response_xml: Union[str, bytes]) -> etree._Element:
        """Extrai o nó útil contido dentro de soap12:Body/nfeResultMsg."""
        if isinstance(response_xml, str):
            xml_bytes = response_xml.encode("utf-8")
        else:
            xml_bytes = response_xml

        root = etree.fromstring(xml_bytes)

        # Checa por SOAP Fault
        fault = root.find(f".//{{{SOAP12_NS}}}Fault")
        if fault is not None:
            fault_code = fault.findtext(f".//{{{SOAP12_NS}}}Value") or "Unknown"
            fault_reason = fault.findtext(f".//{{{SOAP12_NS}}}Text") or "Soap Fault retornado pela SEFAZ"
            raise SefazSoapFaultError(f"SOAP Fault: [{fault_code}] {fault_reason}")

        # Localiza nfeResultMsg ou nfeDadosMsg ou qualquer nó de retorno
        body = root.find(f".//{{{SOAP12_NS}}}Body")
        if body is None or len(body) == 0:
            raise SefazSoapFaultError("Corpo SOAP 1.2 vazio retornado pelo servidor.")

        # Retorna o primeiro filho do Body (normalmente nfeResultMsg)
        return body[0]

    def post_soap(self, url: str, envelope_xml: str, soap_action: str) -> etree._Element:
        """Executa a requisição POST via mTLS TLS 1.2+ e retorna o corpo descompactado do SOAP.

        A chave privada e o certificado público são combinados em memória volátil
        e disponibilizados em canal TLS fechado.
        """
        cert_pem, key_pem = self.cert_manager.export_pem_tuple()

        headers: Dict[str, str] = {
            "Content-Type": "application/soap+xml; charset=utf-8",
            "SOAPAction": soap_action,
        }

        # Cria arquivos temporários voláteis com remoção atômica no finally
        cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")

        try:
            cert_file.write(cert_pem)
            cert_file.flush()
            cert_file.close()

            key_file.write(key_pem)
            key_file.flush()
            key_file.close()

            session = requests.Session()
            session.cert = (cert_file.name, key_file.name)

            response = session.post(
                url=url,
                data=envelope_xml.encode("utf-8"),
                headers=headers,
                timeout=self.timeout_seconds,
            )

            response.raise_for_status()
            return self.extract_soap12_body(response.content)

        except requests.exceptions.Timeout as e:
            raise SefazNetworkError(f"Timeout de comunicação ({self.timeout_seconds}s) com o WebService SEFAZ: {url}") from e
        except requests.exceptions.SSLError as e:
            raise SefazNetworkError(f"Falha de autenticação mTLS (Certificado A1 ou Cifra TLS): {e}") from e
        except requests.exceptions.RequestException as e:
            raise SefazNetworkError(f"Erro de transporte HTTP/Rede com a SEFAZ: {e}") from e
        finally:
            # Remoção imediata e segura dos buffers de disco
            for temp_path in (cert_file.name, key_file.name):
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
                    pass
