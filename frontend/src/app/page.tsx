"use client";

import { useEffect, useState } from "react";
import {
  FileCheck2,
  DollarSign,
  Activity,
  AlertCircle,
  Clock,
  ArrowUpRight,
  ShieldCheck,
  Building,
} from "lucide-react";
import { fetchCertificadoStatus, fetchStatusSefaz, CertificadoStatusResponse, StatusSefazResponse } from "@/lib/api";

export default function DashboardPage() {
  const [certStatus, setCertStatus] = useState<CertificadoStatusResponse | null>(null);
  const [sefazStatus, setSefazStatus] = useState<StatusSefazResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const [cert, sefaz] = await Promise.all([
        fetchCertificadoStatus(),
        fetchStatusSefaz("SP"),
      ]);
      setCertStatus(cert);
      setSefazStatus(sefaz);
      setLoading(false);
    }
    loadData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Dashboard Operacional</h1>
        <p className="text-sm text-slate-400 mt-1">
          Visão geral em tempo real da volumetria fiscal, status dos servidores SEFAZ e certificado A1.
        </p>
      </div>

      {/* Alerta de Certificado Digital se próximo de expirar */}
      {certStatus && certStatus.carregado && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between ${
            (certStatus.dias_para_expirar ?? 999) <= 30
              ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
              : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
          }`}
        >
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-5 h-5 shrink-0" />
            <div>
              <p className="text-sm font-semibold">
                Certificado Digital ICP-Brasil A1:{" "}
                <span className="font-normal">{certStatus.subject || "Carregado"}</span>
              </p>
              <p className="text-xs opacity-90 mt-0.5">
                Válido por mais <b>{certStatus.dias_para_expirar ?? 0} dias</b> (expira em{" "}
                {certStatus.not_valid_after ? new Date(certStatus.not_valid_after).toLocaleDateString("pt-BR") : "N/A"})
              </p>
            </div>
          </div>
          {certStatus.alerta_expiracao && (
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 bg-amber-500/20 border border-amber-500/40 rounded-md">
              Atenção
            </span>
          )}
        </div>
      )}

      {/* Grid de Métricas Principais */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total Emitidas */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Notas no Mês</span>
            <FileCheck2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-3xl font-bold text-white tracking-tight">1.482</span>
            <span className="text-xs text-emerald-400 flex items-center font-medium">
              +12.4% <ArrowUpRight className="w-3.5 h-3.5 ml-0.5" />
            </span>
          </div>
          <p className="text-[11px] text-slate-500">1.210 NF-e mod 55 | 272 NFC-e mod 65</p>
        </div>

        {/* Faturamento Emitido */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Faturado no Mês</span>
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-3xl font-bold text-white tracking-tight">R$ 284.950</span>
            <span className="text-xs text-emerald-400 flex items-center font-medium">
              +8.1% <ArrowUpRight className="w-3.5 h-3.5 ml-0.5" />
            </span>
          </div>
          <p className="text-[11px] text-slate-500">Regime Simples Nacional (Sem excesso)</p>
        </div>

        {/* Status SEFAZ SP */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">SEFAZ Autorizadora</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-center gap-2.5">
            <span className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-lg font-bold text-white">SP - Em Operação</span>
          </div>
          <p className="text-[11px] text-slate-500">
            Código: {sefazStatus?.c_stat || "107"} | Ambiente: {sefazStatus?.ambiente || "Homologação"}
          </p>
        </div>

        {/* Taxa de Autorização */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Taxa de Sucesso</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-3xl font-bold text-emerald-400 tracking-tight">99.8%</span>
            <span className="text-xs text-slate-400 font-medium">0.2% rejeitadas</span>
          </div>
          <p className="text-[11px] text-slate-500">3 correções sugeridas no período</p>
        </div>
      </div>

      {/* Monitor de WebServices Multi-UF */}
      <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">Disponibilidade dos WebServices SEFAZ por Estado</h2>
          <span className="text-xs text-slate-400 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" /> Atualizado há 1 minuto
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-2">
          {[
            { uf: "SP", nome: "São Paulo", status: "Operacional", ping: "42ms" },
            { uf: "BA", nome: "Bahia", status: "Operacional", ping: "68ms" },
            { uf: "MG", nome: "Minas Gerais", status: "Operacional", ping: "55ms" },
            { uf: "RJ", nome: "SVRS (Rio)", status: "Operacional", ping: "49ms" },
            { uf: "PR", nome: "Paraná", status: "Operacional", ping: "51ms" },
          ].map((item) => (
            <div key={item.uf} className="p-3.5 rounded-lg bg-slate-950 border border-slate-800/80 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-white">{item.uf}</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
              </div>
              <p className="text-xs text-slate-400 truncate">{item.nome}</p>
              <div className="flex items-center justify-between pt-1 text-[10px] text-slate-500">
                <span>{item.status}</span>
                <span className="text-emerald-400/80 font-mono">{item.ping}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
