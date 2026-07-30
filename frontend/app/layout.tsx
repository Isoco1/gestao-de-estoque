import type { Metadata } from "next";
import Link from "next/link";
import { ChefHat, LayoutDashboard, Package, UtensilsCrossed } from "lucide-react";
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
    <html lang="pt-BR">
      <body className="min-h-screen">
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
