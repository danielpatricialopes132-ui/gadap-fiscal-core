import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "GADAP Fiscal Hub - Painel Fiscal Operacional",
  description: "Gestão inteligente de NF-e, NFC-e e NFS-e para optantes pelo Simples Nacional",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className={`${inter.className} bg-slate-950 text-slate-100 flex min-h-screen antialiased`}>
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-8 max-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
