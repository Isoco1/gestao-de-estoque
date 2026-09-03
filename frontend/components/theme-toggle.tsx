"use client";

// Alterna entre tema claro e escuro; a escolha persiste em localStorage e é
// reaplicada antes da hidratação pelo script inline do layout (sem "flash").
import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  // Estado inicial neutro no servidor; sincroniza com o <html> após montar
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // localStorage indisponível (ex: modo privado) — o tema vale só na sessão
    }
  }

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={toggle}
      title={isDark ? "Mudar para tema claro" : "Mudar para tema escuro"}
      aria-label={isDark ? "Mudar para tema claro" : "Mudar para tema escuro"}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
