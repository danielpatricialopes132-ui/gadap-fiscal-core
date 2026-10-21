"""Validador local de documentos fiscais eletrônicos contra os schemas oficiais XSD da SEFAZ v4.00.

Evita rejeições básicas na SEFAZ e desperdício de requisições de rede ao validar
a estrutura, ordem de tags e tipos de dados localmente antes da assinatura/envio.
"""

from typing import List, Optional, Tuple, Union
import os
from lxml import etree


# Diretório base dos schemas XSD
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMAS_DIR = os.path.join(CURRENT_DIR, "schemas")
NFE_SCHEMA_FILE = os.path.join(SCHEMAS_DIR, "nfe_v4.00.xsd")


class XsdValidationError(Exception):
    """Exceção levantada quando o XML não atende à especificação XSD da SEFAZ."""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.errors = errors or []


class XsdValidator:
    """Carrega e armazena em cache o schema XSD para validação de XMLs de NF-e / NFC-e."""

    _cached_schema: Optional[etree.XMLSchema] = None

    @classmethod
    def get_schema(cls, xsd_path: Optional[str] = None) -> etree.XMLSchema:
        """Obtém o schema compilado com suporte a cache em memória."""
        path = xsd_path or NFE_SCHEMA_FILE

        if not os.path.exists(path):
            raise FileNotFoundError(f"Arquivo de schema XSD não encontrado no caminho: {path}")

        if cls._cached_schema is None or xsd_path is not None:
            try:
                with open(path, "rb") as f:
                    xsd_doc = etree.parse(f)
                schema = etree.XMLSchema(xsd_doc)
                if xsd_path is None:
                    cls._cached_schema = schema
                return schema
            except Exception as e:
                raise XsdValidationError(f"Falha ao compilar schema XSD '{path}': {e}")

        return cls._cached_schema

    @classmethod
    def validate(
        cls,
        xml_input: Union[bytes, str, etree._Element],
        xsd_path: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Valida o documento XML contra o schema XSD da SEFAZ.

        Args:
            xml_input: Bytes UTF-8, string XML ou etree._Element.
            xsd_path: Caminho opcional para schema alternativo.

        Returns:
            Tuple[bool, List[str]]: (is_valid, lista_de_erros)
        """
        # Parse para elemento etree se fornecido em bytes ou string
        if isinstance(xml_input, str):
            xml_bytes = xml_input.encode("utf-8")
            xml_element = etree.fromstring(xml_bytes)
        elif isinstance(xml_input, bytes):
            xml_element = etree.fromstring(xml_input)
        else:
            xml_element = xml_input

        schema = cls.get_schema(xsd_path)
        is_valid = schema.validate(xml_element)

        errors: List[str] = []
        if not is_valid:
            for error in schema.error_log:
                errors.append(f"Linha {error.line}, Col {error.column}: {error.message}")

        return is_valid, errors

    @classmethod
    def assert_valid(
        cls,
        xml_input: Union[bytes, str, etree._Element],
        xsd_path: Optional[str] = None,
    ) -> None:
        """Valida e lança exceção descritiva caso o XML viole o schema XSD."""
        is_valid, errors = cls.validate(xml_input, xsd_path)
        if not is_valid:
            formatted_errors = "\n - ".join(errors)
            raise XsdValidationError(
                f"XML rejeitado pelo Schema XSD da SEFAZ:\n - {formatted_errors}",
                errors=errors,
            )
