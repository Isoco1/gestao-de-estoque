// Cliente HTTP central do painel: injeta a base URL e o tenant em toda chamada.
// Quando a autenticação JWT for implementada, o token entrará aqui (DRY).

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID ?? "";

export type MeasureUnit = "kg" | "g" | "l" | "ml" | "un";

export interface Ingredient {
  id: string;
  name: string;
  unit: MeasureUnit;
  total_quantity: string; // Decimal serializado como string (soma dos lotes)
  min_stock: string;
  cost_per_unit: string | null;
  is_active: boolean;
}

export interface Lot {
  id: string;
  batch_number: string | null;
  supplier_brand: string;
  unit_cost: string;
  initial_quantity: string;
  current_quantity: string;
  manufacturing_date: string | null;
  expiration_date: string | null;
  created_at: string;
}

export interface IngredientLots {
  ingredient: Ingredient;
  lots: Lot[];
  total_quantity: string;
  weighted_average_cost: string | null;
}

export interface ExpirationAlertItem {
  lot_id: string;
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  supplier_brand: string;
  batch_number: string | null;
  expiration_date: string;
  days_to_expiration: number;
  status: "vencido" | "a_vencer";
  quantity: string;
  unit_cost: string;
  value_at_risk: string;
}

export interface ExpirationAlerts {
  reference_date: string;
  days_window: number;
  expired: ExpirationAlertItem[];
  expiring_soon: ExpirationAlertItem[];
  total_value_at_risk: string;
}

export interface ZapiStatus {
  connected: boolean;
  phone_number: string | null;
  status_message: string;
}

export interface RecipeItem {
  id: string;
  ingredient_id: string;
  quantity: string;
  ingredient: Ingredient;
}

export interface Product {
  id: string;
  name: string;
  price: string;
  is_active: boolean;
  recipe_items: RecipeItem[];
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-ID": TENANT_ID,
      ...options.headers,
    },
  });

  if (!response.ok) {
    // Repassa a mensagem de erro da API para a interface
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Erro ${response.status}`);
  }
  // DELETE 204 não tem corpo
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  // Ingredientes
  listIngredients: (onlyCritical = false) =>
    request<Ingredient[]>(`/ingredients?only_critical=${onlyCritical}`),
  createIngredient: (data: {
    name: string;
    unit: MeasureUnit;
    stock_quantity: string;
    min_stock: string;
  }) => request<Ingredient>("/ingredients", { method: "POST", body: JSON.stringify(data) }),
  // Exclusão lógica: justificativa obrigatória (mínimo 5 caracteres)
  deleteIngredient: (id: string, reason: string) =>
    request<void>(`/ingredients/${id}`, {
      method: "DELETE",
      body: JSON.stringify({ reason }),
    }),

  // Lotes (janela de detalhes do ingrediente)
  listLots: (ingredientId: string) =>
    request<IngredientLots>(`/ingredients/${ingredientId}/lots`),
  createLot: (
    ingredientId: string,
    data: {
      batch_number?: string | null;
      supplier_brand: string;
      unit_cost: string;
      quantity: string;
      manufacturing_date?: string | null;
      expiration_date?: string | null;
    }
  ) =>
    request<Lot>(`/ingredients/${ingredientId}/lots`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Dashboard: alertas de vencimento e status do WhatsApp
  expirationAlerts: (days = 7) =>
    request<ExpirationAlerts>(`/inventory/expiration-alerts?days=${days}`),
  zapiStatus: () => request<ZapiStatus>("/integrations/z-api/status"),

  // Produtos e ficha técnica
  listProducts: () => request<Product[]>("/products"),
  createProduct: (data: { name: string; price: string }) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(data) }),
  saveRecipe: (productId: string, items: { ingredient_id: string; quantity: string }[]) =>
    request<Product>(`/products/${productId}/recipe`, {
      method: "PUT",
      body: JSON.stringify({ items }),
    }),
};
