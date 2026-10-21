"use client";

import { useState } from "react";
import {
  HelpCircle,
  BookOpen,
  Send,
  MessageSquare,
  FileCheck,
  ShieldAlert,
  Download,
  PhoneCall,
  Search,
  ExternalLink,
  ChevronRight,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";

interface FAQItem {
  pergunta: string;
  resposta: string;
  categoria: "emissao" | "whatsapp" | "sefaz" | "certificado";
}

const FAQ_ITEMS: FAQItem[] = [
  {
    pergunta: "Como o cliente recebe o DANFE em PDF pelo WhatsApp?",
    resposta:
      "Ao cadastrar a venda no ERP ou no Hub, basta informar o número de celular no campo 'destinatario.telefone_whatsapp'. Assim que a SEFAZ autorizar a nota (cStat 100), nosso disparador em segundo plano envia automaticamente uma mensagem amigável e o arquivo PDF anexo para download direto no aparelho do cliente.",
    categoria: "whatsapp",
  },
  {
    pergunta: "O que fazer se o envio do WhatsApp falhar por falta de bateria ou sinal?",
    resposta:
      "A autorização fiscal da nota nunca é cancelada ou prejudicada. Na 'Central de Notas', você pode clicar no botão 'Reenviar WhatsApp' ao lado de qualquer nota autorizada, informar um número novo ou o mesmo e reenviar o DANFE imediatamente.",
    categoria: "whatsapp",
  },
  {
    pergunta: "Qual a diferença entre NF-e (Modelo 55) e NFC-e (Modelo 65)?",
    resposta:
      "A NFC-e (Nota Fiscal de Consumidor Eletrônica) é voltada para vendas presenciais no varejo (balcão) para pessoas físicas ou jurídicas sem aproveitamento de crédito, substituindo o cupom fiscal tradicional (impresso em bobina térmica de 80mm). A NF-e (Modelo 55) é usada para atacado, entrega interestadual e operações comerciais mais completas (impresso em folha A4).",
    categoria: "emissao",
  },
  {
    pergunta: "Como enviar os arquivos mensais para o escritório de contabilidade?",
    resposta:
      "Acesse o menu 'Fechamento Contábil', selecione o mês e o ano desejados e clique em 'Exportar Pacote Contábil (.ZIP)'. O sistema reúne todos os XMLs autorizados (procNFe) e DANFEs em PDF em um único arquivo compactado pronto para ser anexado e enviado ao contador.",
    categoria: "emissao",
  },
  {
    pergunta: "Como sei se meu Certificado Digital A1 está perto de vencer?",
    resposta:
      "No topo do Dashboard e no menu 'Configurações', o sistema monitora diariamente a data limite da cadeia ICP-Brasil. Um alerta amarelo surge com 30 dias de antecedência, e vermelho com 15 dias, dando tempo hábil para a renovação na autoridade certificadora.",
    categoria: "certificado",
  },
  {
    pergunta: "O que significa a rejeição 'cStat 539: Duplicidade com diferença na Chave de Acesso'?",
    resposta:
      "Significa que uma nota com este mesmo CNPJ, Série e Número já foi emitida anteriormente na SEFAZ com outros dados ou data. Para resolver, basta alterar a numeração da nota fiscal para o próximo número livre no seu ERP.",
    categoria: "sefaz",
  },
];

export default function AjudaPage() {
  const [busca, setBusca] = useState("");
  const [categoriaAtiva, setCategoriaAtiva] = useState<string>("todas");
  const [itemAberto, setItemAberto] = useState<number | null>(0);

  const faqFiltrado = FAQ_ITEMS.filter((item) => {
    const matchCategoria = categoriaAtiva === "todas" || item.categoria === categoriaAtiva;
    const matchBusca =
      item.pergunta.toLowerCase().includes(busca.toLowerCase()) ||
      item.resposta.toLowerCase().includes(busca.toLowerCase());
    return matchCategoria && matchBusca;
  });

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-emerald-400 text-sm font-semibold mb-1">
          <BookOpen className="w-4 h-4" />
          <span>MANUAIS E DOCUMENTAÇÃO</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Central de Ajuda & Guia Operacional</h1>
        <p className="text-slate-400 mt-1">
          Instruções práticas, procedimentos fiscais para o Simples Nacional e solução rápida de dúvidas.
        </p>
      </div>

      {/* Quick Cards de Operações Essenciais */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 relative overflow-hidden group hover:border-slate-700 transition-all">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4">
            <FileCheck className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-white text-lg mb-2">Fluxo de Emissão</h3>
          <p className="text-sm text-slate-400 leading-relaxed mb-4">
            Emita notas em conformidade com o Simples Nacional (CRT 1) com cálculo tributário de CSOSN e alíquotas PGDAS automáticas.
          </p>
          <div className="text-xs text-emerald-400 font-medium flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>Ver regras fiscais</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 relative overflow-hidden group hover:border-slate-700 transition-all">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4">
            <MessageSquare className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-white text-lg mb-2">WhatsApp Evolution API</h3>
          <p className="text-sm text-slate-400 leading-relaxed mb-4">
            Envio automatizado de DANFEs em PDF assinado para o cliente logo após a autorização na SEFAZ com link seguro.
          </p>
          <div className="text-xs text-emerald-400 font-medium flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>Diagnosticar canal</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 relative overflow-hidden group hover:border-slate-700 transition-all">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-4">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-white text-lg mb-2">Diagnóstico de Rejeições</h3>
          <p className="text-sm text-slate-400 leading-relaxed mb-4">
            Consulte códigos cStat da SEFAZ traduzidos para linguagem simples com instruções passo a passo para o operador.
          </p>
          <div className="text-xs text-amber-400 font-medium flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>Acessar tabela de erros</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </div>
        </div>
      </div>

      {/* Caixa de Busca e Filtros */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <div className="flex flex-col md:flex-row gap-4 justify-between items-center">
          <div className="relative w-full md:w-96">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Pesquisar manuais, dúvidas ou erros..."
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 placeholder:text-slate-600"
            />
          </div>

          <div className="flex flex-wrap gap-2 w-full md:w-auto">
            {[
              { id: "todas", label: "Todas as Dúvidas" },
              { id: "whatsapp", label: "WhatsApp" },
              { id: "emissao", label: "Emissão & Contábil" },
              { id: "sefaz", label: "SEFAZ / Rejeições" },
              { id: "certificado", label: "Certificado A1" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setCategoriaAtiva(tab.id)}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  categoriaAtiva === tab.id
                    ? "bg-emerald-600 text-white"
                    : "bg-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Lista de Perguntas e Respostas */}
        <div className="divide-y divide-slate-800/80 pt-2">
          {faqFiltrado.length === 0 ? (
            <div className="text-center py-10 text-slate-500 text-sm">
              Nenhum tópico encontrado para a busca "{busca}".
            </div>
          ) : (
            faqFiltrado.map((item, idx) => {
              const isAberto = itemAberto === idx;
              return (
                <div key={idx} className="py-4">
                  <button
                    onClick={() => setItemAberto(isAberto ? null : idx)}
                    className="w-full text-left flex items-center justify-between text-base font-semibold text-white hover:text-emerald-400 transition-colors"
                  >
                    <span>{item.pergunta}</span>
                    <ChevronRight
                      className={`w-4 h-4 text-slate-500 transition-transform ${isAberto ? "rotate-90 text-emerald-400" : ""}`}
                    />
                  </button>
                  {isAberto && (
                    <div className="mt-3 text-sm text-slate-400 leading-relaxed pl-2 border-l-2 border-emerald-500">
                      {item.resposta}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Sessão de Suporte Técnico */}
      <div className="bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-900/30 rounded-xl p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-1">
          <h4 className="text-white font-semibold text-base">Precisa de assistência técnica especializada?</h4>
          <p className="text-sm text-slate-400">
            Nossa equipe técnica e fiscal está pronta para auxiliar em homologações de novos estados e emissão em contingência.
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <a
            href="https://wa.me/5511913192703"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-md shadow-emerald-900/30"
          >
            <PhoneCall className="w-4 h-4" />
            <span>Suporte WhatsApp</span>
          </a>
        </div>
      </div>
    </div>
  );
}
