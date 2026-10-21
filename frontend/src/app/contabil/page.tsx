"use client";

import { useState } from "react";
import { FolderArchive, Download, CheckCircle, Calendar, FileArchive, ArrowDownToLine } from "lucide-react";

export default function FechamentoContabilPage() {
  const [mesSelecionado, setMesSelecionado] = useState("2026-10");
  const [gerando, setGerando] = useState(false);
  const [sucesso, setSucesso] = useState(false);

  const handleDownloadPacote = () => {
    setGerando(true);
    setSucesso(false);

    setTimeout(() => {
      setGerando(false);
      setSucesso(true);

      // Simulação do download do ZIP contábil
      const dummyContent = "Conteúdo simulado de pacote fiscal contábil ZIP com XMLs e DANFEs";
      const blob = new Blob([dummyContent], { type: "application/zip" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `GADAP_Fiscal_Pacote_${mesSelecionado}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    }, 1500);
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Fechamento Fiscal & Contábil</h1>
        <p className="text-sm text-slate-400 mt-1">
          Exporte o lote completo contendo todos os XMLs autorizados (&lt;nfeProc&gt;), eventos e DANFEs em PDF para a contabilidade.
        </p>
      </div>

      {/* Card de Configuração do Pacote */}
      <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-6">
        <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
          <FolderArchive className="w-5 h-5 text-emerald-400" />
          <h2 className="text-base font-semibold text-white">Geração de Pacote Mensal para a Contabilidade</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-slate-300 block mb-1.5">
              Mês de Competência
            </label>
            <input
              type="month"
              value={mesSelecionado}
              onChange={(e) => setMesSelecionado(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-slate-300 block mb-1.5">
              Conteúdo do Pacote ZIP
            </label>
            <div className="p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-400 space-y-1">
              <p>✔ XMLs autorizados de NF-e (55) e NFC-e (65)</p>
              <p>✔ Eventos fiscais de Cancelamento e CC-e (&lt;procEventoNFe&gt;)</p>
              <p>✔ DANFEs em PDF de todas as notas emitidas</p>
            </div>
          </div>
        </div>

        {/* Resumo da Competência */}
        <div className="p-4 rounded-lg bg-slate-950 border border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
          <span>Total de Notas no Período: <b className="text-white">1.482</b></span>
          <span>Valor Faturado Acumulado: <b className="text-emerald-400">R$ 284.950,00</b></span>
          <span>Tamanho Estimado: <b className="text-white">~14.2 MB</b></span>
        </div>

        {/* Botão de Disparo */}
        <div className="pt-2 flex items-center gap-4">
          <button
            onClick={handleDownloadPacote}
            disabled={gerando}
            className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-white font-medium text-sm rounded-lg transition-colors shadow-sm"
          >
            {gerando ? (
              <>Compactando XMLs e PDFs...</>
            ) : (
              <>
                <ArrowDownToLine className="w-4 h-4" /> Baixar Pacote Contábil (.zip)
              </>
            )}
          </button>

          {sucesso && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
              <CheckCircle className="w-4 h-4" /> Pacote gerado e baixado com sucesso!
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
