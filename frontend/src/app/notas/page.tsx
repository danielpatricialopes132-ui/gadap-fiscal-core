"use client";

import { useState } from "react";
import { Search, Download, FileText, CheckCircle2, XCircle, AlertCircle, Eye, Filter } from "lucide-react";
import { NotaFiscalItem } from "@/lib/api";

const MOCK_NOTAS: NotaFiscalItem[] = [
  {
    id: "1",
    chave_acesso: "35261011222333000181550010000012341297617328",
    numero: 1234,
    serie: 1,
    modelo: "55",
    tipo: "NFE",
    destinatario_nome: "CLIENTE TESTE SAO PAULO LTDA",
    destinatario_doc: "99.888.777/0001-61",
    valor_total: 290.0,
    data_emissao: "2026-10-21 12:45",
    status: "AUTORIZADA",
    protocolo: "135240000000001",
  },
  {
    id: "2",
    chave_acesso: "35261011222333000181650010000005431837461921",
    numero: 543,
    serie: 1,
    modelo: "65",
    tipo: "NFCE",
    destinatario_nome: "CONSUMIDOR FINAL",
    destinatario_doc: "000.000.000-00",
    valor_total: 45.9,
    data_emissao: "2026-10-21 11:30",
    status: "AUTORIZADA",
    protocolo: "135240000000002",
  },
  {
    id: "3",
    chave_acesso: "35261011222333000181550010000012331998471624",
    numero: 1233,
    serie: 1,
    modelo: "55",
    tipo: "NFE",
    destinatario_nome: "DISTRIBUIDORA NORTE LTDA",
    destinatario_doc: "44.555.666/0001-22",
    valor_total: 1250.0,
    data_emissao: "2026-10-21 10:15",
    status: "CANCELADA",
    protocolo: "135240000000003",
  },
  {
    id: "4",
    chave_acesso: "35261011222333000181550010000012321122334455",
    numero: 1232,
    serie: 1,
    modelo: "55",
    tipo: "NFE",
    destinatario_nome: "MERCADO MODELO BAHIA EIRELI",
    destinatario_doc: "12.345.678/0001-99",
    valor_total: 820.0,
    data_emissao: "2026-10-20 18:20",
    status: "REJEITADA",
  },
];

export default function CentralNotasPage() {
  const [busca, setBusca] = useState("");
  const [filtroStatus, setFiltroStatus] = useState<string>("TODOS");

  const notasFiltradas = MOCK_NOTAS.filter((nota) => {
    const matchBusca =
      nota.chave_acesso.toLowerCase().includes(busca.toLowerCase()) ||
      nota.destinatario_nome.toLowerCase().includes(busca.toLowerCase()) ||
      nota.numero.toString().includes(busca);

    if (filtroStatus === "TODOS") return matchBusca;
    return matchBusca && nota.status === filtroStatus;
  });

  const handleDownloadXml = (chave: string) => {
    const dummyXml = `<?xml version="1.0" encoding="UTF-8"?><nfeProc versao="4.00"><NFe><infNFe Id="NFe${chave}"></infNFe></NFe></nfeProc>`;
    const blob = new Blob([dummyXml], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${chave}.xml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleVisualizarDanfe = (chave: string) => {
    window.open(`/api/v1/dfe/danfe/pdf?chave=${chave}`, "_blank");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Central de Notas Fiscais</h1>
          <p className="text-sm text-slate-400 mt-1">
            Consulte, visualize DANFE em PDF e baixe os arquivos XML autorizados pela SEFAZ.
          </p>
        </div>
      </div>

      {/* Barra de Filtros e Busca */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl bg-slate-900 border border-slate-800">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar por Chave de 44 dígitos, Destinatário ou Nº..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={filtroStatus}
            onChange={(e) => setFiltroStatus(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-emerald-500"
          >
            <option value="TODOS">Todos os Status</option>
            <option value="AUTORIZADA">Autorizadas</option>
            <option value="CANCELADA">Canceladas</option>
            <option value="REJEITADA">Rejeitadas</option>
          </select>
        </div>
      </div>

      {/* Tabela de Notas */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4">Doc / Número</th>
                <th className="py-3 px-4">Chave de Acesso</th>
                <th className="py-3 px-4">Destinatário</th>
                <th className="py-3 px-4">Valor Total</th>
                <th className="py-3 px-4">Data Emissão</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {notasFiltradas.map((nota) => (
                <tr key={nota.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <span className="font-bold text-white block">
                      {nota.tipo} Nº {nota.numero}
                    </span>
                    <span className="text-[11px] text-slate-500">Série {nota.serie}</span>
                  </td>
                  <td className="py-3.5 px-4 whitespace-nowrap font-mono text-xs text-slate-400">
                    {nota.chave_acesso.slice(0, 10)}...{nota.chave_acesso.slice(-8)}
                  </td>
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <span className="text-white block truncate max-w-xs">{nota.destinatario_nome}</span>
                    <span className="text-[11px] text-slate-500">{nota.destinatario_doc}</span>
                  </td>
                  <td className="py-3.5 px-4 whitespace-nowrap font-bold text-emerald-400">
                    R$ {nota.valor_total.toFixed(2)}
                  </td>
                  <td className="py-3.5 px-4 whitespace-nowrap text-xs text-slate-400">
                    {nota.data_emissao}
                  </td>
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    {nota.status === "AUTORIZADA" && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Autorizada
                      </span>
                    )}
                    {nota.status === "CANCELADA" && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
                        <AlertCircle className="w-3.5 h-3.5" /> Cancelada
                      </span>
                    )}
                    {nota.status === "REJEITADA" && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-500/10 text-red-400 border border-red-500/20">
                        <XCircle className="w-3.5 h-3.5" /> Rejeitada
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 whitespace-nowrap text-right space-x-2">
                    <button
                      onClick={() => handleVisualizarDanfe(nota.chave_acesso)}
                      title="Visualizar DANFE PDF"
                      className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDownloadXml(nota.chave_acesso)}
                      title="Download XML Autorizado"
                      className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-emerald-400 hover:bg-slate-700 transition-colors"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
