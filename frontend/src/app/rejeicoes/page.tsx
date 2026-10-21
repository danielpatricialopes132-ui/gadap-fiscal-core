"use client";

import { AlertTriangle, HelpCircle, ArrowRight, Lightbulb, Search } from "lucide-react";
import { useState } from "react";
import { RejeicaoItem } from "@/lib/api";

const MOCK_REJEICOES: RejeicaoItem[] = [
  {
    id: "1",
    c_stat: "699",
    x_motivo: "Percentual do ICMS Interestadual para a UF de destino difere do previsto",
    explicacao_amigavel:
      "A SEFAZ rejeitou porque foi informada a partilha do DIFAL em uma venda interestadual B2C emitida por empresa optante pelo Simples Nacional.",
    acao_sugerida:
      "O GADAP Fiscal Core removeu automaticamente a tag <ICMSUFDest> conforme a liminar da ADI 5464 do STF. Reenvie o documento.",
    tipo_documento: "NF-e (55)",
    data_ocorrencia: "2026-10-21 10:14",
  },
  {
    id: "2",
    c_stat: "539",
    x_motivo: "Duplicidade de NF-e, com diferença na Chave de Acesso",
    explicacao_amigavel:
      "O número da nota já foi autorizado anteriormente com outro conteúdo de produtos ou data diferente.",
    acao_sugerida:
      "Incremente o número da NF-e para o próximo sequencial livre ou consulte o histórico da nota anterior.",
    tipo_documento: "NF-e (55)",
    data_ocorrencia: "2026-10-20 18:20",
  },
  {
    id: "3",
    c_stat: "384",
    x_motivo: "CSOSN incompatível na operação com Não Contribuinte",
    explicacao_amigavel:
      "O código CSOSN selecionado não é permitido para o tipo de destinatário informado.",
    acao_sugerida:
      "Para vendas a não contribuintes no Simples Nacional utilize prioritariamente CSOSN 102 ou 500 (em caso de ST prévia).",
    tipo_documento: "NFC-e (65)",
    data_ocorrencia: "2026-10-20 14:05",
  },
  {
    id: "4",
    c_stat: "280",
    x_motivo: "Certificado Transmissor inválido",
    explicacao_amigavel:
      "O certificado digital A1 ICP-Brasil está vencido, revogado ou com a cadeia de certificados desatualizada.",
    acao_sugerida:
      "Acesse a aba 'Configurações' do Fiscal Hub e faça o upload do novo arquivo .pfx válido com sua respectiva senha.",
    tipo_documento: "SEFAZ Geral",
    data_ocorrencia: "2026-10-19 09:30",
  },
];

export default function DiagnosticoRejeicoesPage() {
  const [termo, setTermo] = useState("");

  const filtradas = MOCK_REJEICOES.filter(
    (r) =>
      r.c_stat.includes(termo) ||
      r.x_motivo.toLowerCase().includes(termo.toLowerCase()) ||
      r.explicacao_amigavel.toLowerCase().includes(termo.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Diagnóstico de Rejeições SEFAZ</h1>
        <p className="text-sm text-slate-400 mt-1">
          Guia inteligente de suporte para resolução de erros fiscais em linguagem simples para os operadores do ERP.
        </p>
      </div>

      {/* Busca rápida de cStat */}
      <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-3">
        <Search className="w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="Pesquise pelo código do erro (ex: 699, 539, 280) ou palavras-chave..."
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          className="w-full bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
        />
      </div>

      {/* Lista de Rejeições */}
      <div className="space-y-4">
        {filtradas.map((rej) => (
          <div
            key={rej.id}
            className="p-5 rounded-xl bg-slate-900 border border-slate-800/80 hover:border-slate-700 transition-all space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="px-2.5 py-1 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-bold font-mono">
                  cStat {rej.c_stat}
                </span>
                <span className="text-xs text-slate-400 font-medium">{rej.tipo_documento}</span>
              </div>
              <span className="text-xs text-slate-500">{rej.data_ocorrencia}</span>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-white">{rej.x_motivo}</h3>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                {rej.explicacao_amigavel}
              </p>
            </div>

            {/* Ação Sugerida */}
            <div className="p-3.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20 flex items-start gap-3 text-xs text-emerald-300">
              <Lightbulb className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-emerald-400">Como corrigir: </span>
                {rej.acao_sugerida}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
