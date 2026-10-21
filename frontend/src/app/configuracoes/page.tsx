"use client";

import { useState } from "react";
import { Settings, ShieldCheck, Key, Save, CheckCircle2, Upload, Server } from "lucide-react";

export default function ConfiguracoesPage() {
  const [ambiente, setAmbiente] = useState<"homologacao" | "producao">("homologacao");
  const [cscId, setCscId] = useState("000001");
  const [cscToken, setCscToken] = useState("0123456789ABCDEF");
  const [senhaCert, setSenhaCert] = useState("");
  const [salvo, setSalvo] = useState(false);

  const handleSalvar = (e: React.FormEvent) => {
    e.preventDefault();
    setSalvo(true);
    setTimeout(() => setSalvo(false), 3000);
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Configurações Fiscais</h1>
        <p className="text-sm text-slate-400 mt-1">
          Gerencie o ambiente de emissão da SEFAZ, credenciais de NFC-e (CSC) e Certificado Digital A1.
        </p>
      </div>

      <form onSubmit={handleSalvar} className="space-y-6">
        {/* 1. Comutador de Ambiente SEFAZ */}
        <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
            <Server className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-semibold text-white">Ambiente de Operação (SEFAZ)</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <label
              className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start gap-3 ${
                ambiente === "homologacao"
                  ? "bg-emerald-500/10 border-emerald-500 text-white"
                  : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
              }`}
            >
              <input
                type="radio"
                name="ambiente"
                value="homologacao"
                checked={ambiente === "homologacao"}
                onChange={() => setAmbiente("homologacao")}
                className="mt-1 accent-emerald-500"
              />
              <div>
                <span className="font-semibold block text-sm">Homologação (tpAmb = 2)</span>
                <span className="text-xs text-slate-400 block mt-1">
                  Ambiente de testes oficial da SEFAZ. As notas não possuem valor fiscal e recebem marca d&apos;água.
                </span>
              </div>
            </label>

            <label
              className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start gap-3 ${
                ambiente === "producao"
                  ? "bg-emerald-500/10 border-emerald-500 text-white"
                  : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
              }`}
            >
              <input
                type="radio"
                name="ambiente"
                value="producao"
                checked={ambiente === "producao"}
                onChange={() => setAmbiente("producao")}
                className="mt-1 accent-emerald-500"
              />
              <div>
                <span className="font-semibold block text-sm">Produção (tpAmb = 1)</span>
                <span className="text-xs text-slate-400 block mt-1">
                  Emissão real com validade jurídica perante o Fisco estadual e federal.
                </span>
              </div>
            </label>
          </div>
        </div>

        {/* 2. Certificado Digital ICP-Brasil A1 */}
        <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-semibold text-white">Certificado Digital ICP-Brasil A1</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1.5">
                Arquivo do Certificado (.pfx / .p12)
              </label>
              <div className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-lg p-4 text-center cursor-pointer bg-slate-950 transition-colors">
                <Upload className="w-5 h-5 text-slate-400 mx-auto mb-2" />
                <span className="text-xs text-slate-300 font-medium block">
                  Clique ou arraste seu arquivo .pfx
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  Carregado em memória volátil de forma segura
                </span>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1.5">
                Senha da Chave Privada
              </label>
              <input
                type="password"
                placeholder="Digite a senha do certificado..."
                value={senhaCert}
                onChange={(e) => setSenhaCert(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <span className="text-[11px] text-slate-500 mt-1.5 block">
                Nunca compartilhe a senha do certificado digital.
              </span>
            </div>
          </div>
        </div>

        {/* 3. Parâmetros NFC-e (Código de Segurança do Contribuinte - CSC) */}
        <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
            <Key className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-semibold text-white">Credenciais CSC (NFC-e Modelo 65)</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1.5">
                Identificador do Token (IdToken / CSC ID)
              </label>
              <input
                type="text"
                placeholder="Ex: 000001"
                value={cscId}
                onChange={(e) => setCscId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1.5">
                Código Alfanumérico do CSC (Token)
              </label>
              <input
                type="text"
                placeholder="Ex: 0123456789ABCDEF..."
                value={cscToken}
                onChange={(e) => setCscToken(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Botão Salvar */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm rounded-lg transition-colors shadow-sm"
          >
            <Save className="w-4 h-4" /> Salvar Configurações
          </button>
          {salvo && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
              <CheckCircle2 className="w-4 h-4" /> Configurações salvas e aplicadas!
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
