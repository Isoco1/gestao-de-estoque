import type { Metadata } from "next";
import Link from "next/link";
import { ChefHat, LayoutDashboard, Package, UtensilsCrossed } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gestão de Estoque",
  description: "Gestão de estoque para restaurantes, deliveries e mercados",
};

// Itens do menu lateral (adicionar novas páginas aqui)
const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/ingredientes", label: "Ingredientes", icon: Package },
  { href: "/fichas-tecnicas", label: "Fichas Técnicas", icon: UtensilsCrossed },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: a classe "dark" é aplicada antes da hidratação
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        {/* Reaplica o tema salvo ANTES do primeiro paint (evita flash claro) */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              'try{if(localStorage.getItem("theme")==="dark")document.documentElement.classList.add("dark")}catch(e){}',
          }}
        />
      </head>
      <body className="min-h-screen">
        {/* Alternador de tema: canto superior direito, visível em toda página */}
        <div className="fixed right-4 top-4 z-50">
          <ThemeToggle />
        </div>
        <div className="flex min-h-screen">
          {/* Sidebar */}
          <aside className="w-60 shrink-0 border-r bg-card p-4">
            <div className="mb-8 flex items-center gap-2 px-2">
              <ChefHat className="h-6 w-6 text-primary" />
              <span className="text-lg font-bold">Gestão de Estoque</span>
            </div>
            <nav className="space-y-1">
              {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              ))}
            </nav>
          </aside>

          {/* Conteúdo */}
          <main className="flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
