# Gadap Fiscal Core - Motor DF-e

Motor de Emissão de Documentos Fiscais Eletrônicos (NF-e modelo 55, NFC-e modelo 65 e NFS-e) focado no **Simples Nacional (CRT = 1)**, desenvolvido em Python.

## Recursos Implementados

- **Gestão Segura de Certificados Digitais A1 (.pfx / .p12)**:
  - Carga e extração de chaves privadas e certificados X.509 ICP-Brasil 100% em memória.
  - Exportação para mTLS sem persistência de chaves desprotegidas em disco.
  - Verificação de validade e data de expiração.
- **Configurações e Ambientes DF-e**:
  - Homologação (`tpAmb = 2`) e Produção (`tpAmb = 1`).
  - Suporte a credenciais de NFC-e (CSC Id e Token).
  - Endpoints SEFAZ para SP e SVRS.
- **Modelo Canônico de Entrada**:
  - Schemas Pydantic V2 isolando a API da complexidade dos XMLs da SEFAZ.
  - Tipagem estrita com `Decimal` para evitar desvios de precisão de ponto flutuante.
- **Motor Tributário Simples Nacional**:
  - Arredondamento Half-Up conforme **ABNT NBR 5891**.
  - Regras específicas para CSOSN 101 (cálculo de crédito de ICMS), 102/103 (sem crédito) e 500 (ST retido anteriormente).
  - Enquadramento automático de PIS/COFINS (CST 49/99).
  - Geração de mensagens fiscais obrigatórias (Resolução CGSN nº 140/2018).

## Testes

```bash
pytest tests/ -v
```
