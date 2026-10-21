"""Módulo para geração e validação da Chave de Acesso de 44 dígitos da SEFAZ.

Padrão:
cUF (2) + AAMM (4) + CNPJ (14) + mod (2) + serie (3) + nNF (9) + tpEmis (1) + cNF (8) + cDV (1)
Dígito Verificador calculado via Módulo 11 (pesos de 2 a 9).
"""

import random
from app.core.uf_matrix import get_cuf_by_uf


def calculate_mod11_dv(chave_43: str) -> int:
    """Calcula o dígito verificador (cDV) via algoritmo Módulo 11 (pesos de 2 a 9).

    Regra SEFAZ (Manual de Orientação do Contribuinte - MOC):
    Multiplicam-se os 43 dígitos, da direita para a esquerda, pelos pesos de 2 a 9
    (repetindo o ciclo 2..9).
    Soma-se o resultado das multiplicações.
    Resto = Soma % 11.
    Se Resto == 0 ou Resto == 1: DV = 0
    Senão: DV = 11 - Resto.
    """
    if len(chave_43) != 43 or not chave_43.isdigit():
        raise ValueError(f"Chave de 43 dígitos inválida para cálculo do DV: {chave_43}")

    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    peso_idx = 0

    for digito in reversed(chave_43):
        soma += int(digito) * pesos[peso_idx]
        peso_idx = (peso_idx + 1) % len(pesos)

    resto = soma % 11
    if resto in (0, 1):
        return 0
    return 11 - resto


def generate_cnf() -> str:
    """Gera código numérico aleatório de 8 dígitos para o cNF."""
    return f"{random.randint(10000000, 99999999):08d}"


def build_access_key(
    c_uf: str,
    ano_mes: str,
    cnpj: str,
    modelo: str,
    serie: int,
    numero_nf: int,
    tp_emis: str = "1",
    c_nf: str = "",
) -> str:
    """Monta a chave de acesso completa de 44 dígitos com cDV calculado determinísticamente.

    Args:
        c_uf: Código numérico da UF (2 dígitos) ou sigla da UF (ex: '35', '29', 'SP', 'BA')
        ano_mes: AAMM da emissão (ex: '2610')
        cnpj: CNPJ do emitente (14 dígitos numéricos)
        modelo: '55' (NF-e) ou '65' (NFC-e)
        serie: Série da nota (1 a 999)
        numero_nf: Número da nota (1 a 999999999)
        tp_emis: Tipo de emissão ('1'=Normal)
        c_nf: Código numérico de 8 dígitos. Se vazio, é gerado aleatoriamente.

    Returns:
        str: Chave de acesso com 44 dígitos.
    """
    # Lê obrigatoriamente a partir de uf_matrix se for sigla ou código
    c_uf_clean = c_uf.strip().upper()
    if len(c_uf_clean) == 2 and not c_uf_clean.isdigit():
        c_uf_fmt = get_cuf_by_uf(c_uf_clean)
    else:
        c_uf_fmt = f"{int(c_uf_clean):02d}"

    ano_mes_fmt = "".join(filter(str.isdigit, ano_mes))
    if len(ano_mes_fmt) != 4:
        raise ValueError(f"AAMM deve conter exatamente 4 dígitos numéricos (ex: 2610): {ano_mes}")

    cnpj_clean = "".join(filter(str.isdigit, cnpj))
    if len(cnpj_clean) != 14:
        raise ValueError(f"CNPJ deve conter 14 dígitos numéricos: {cnpj}")

    mod_fmt = f"{int(modelo):02d}"
    serie_fmt = f"{int(serie):03d}"
    nnf_fmt = f"{int(numero_nf):09d}"
    tp_emis_fmt = str(tp_emis)

    cnf_clean = "".join(filter(str.isdigit, c_nf)) if c_nf else ""
    if len(cnf_clean) != 8:
        cnf_clean = generate_cnf()

    chave_43 = (
        f"{c_uf_fmt}"
        f"{ano_mes_fmt}"
        f"{cnpj_clean}"
        f"{mod_fmt}"
        f"{serie_fmt}"
        f"{nnf_fmt}"
        f"{tp_emis_fmt}"
        f"{cnf_clean}"
    )

    cdv = calculate_mod11_dv(chave_43)
    return f"{chave_43}{cdv}"


def validate_access_key(chave: str) -> bool:
    """Valida se uma chave de 44 dígitos possui tamanho, caracteres e dígito verificador corretos."""
    clean_key = "".join(filter(str.isdigit, chave))
    if len(clean_key) != 44:
        return False

    chave_43 = clean_key[:43]
    cdv_esperado = int(clean_key[43])
    return calculate_mod11_dv(chave_43) == cdv_esperado
