import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// Helper padrão do Shadcn/UI para compor classes Tailwind sem conflitos
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Formata "YYYY-MM-DD" para pt-BR sem efeito de fuso horário. */
export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR");
}

/** Dias entre hoje e uma data "YYYY-MM-DD" (negativo = no passado). */
export function daysUntil(iso: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(`${iso}T00:00:00`);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

/** Rótulo e variante do badge de vencimento (dias negativos = vencido). */
export function expirationBadge(days: number): {
  label: string;
  variant: "destructive" | "warning";
} {
  return days < 0
    ? { label: `Vencido há ${-days}d`, variant: "destructive" }
    : { label: `Vence em ${days}d`, variant: "warning" };
}
