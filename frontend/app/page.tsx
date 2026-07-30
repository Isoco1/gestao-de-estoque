"use client";

// Dashboard: estoque crítico, validade de perecíveis e status do WhatsApp.
import { useEffect, useState } from "react";
import {
  AlertTriangle, CalendarClock, Package, Smartphone, TrendingDown,
} from "lucide-react";
import {
  api,
  type ExpirationAlerts,
  type Ingredient,
  type ZapiStatus,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function DashboardPage() {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [alerts, setAlerts] = useState<ExpirationAlerts | null>(null);
  const [zapi, setZapi] = useState<ZapiStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // As três consultas são independentes; falha em uma não derruba as outras
    Promise.allSettled([
      api.listIngredients().then(setIngredients),
      api.expirationAlerts(7).then(setAlerts),
      api.zapiStatus().then(setZapi),
    ]).then((results) => {
      const firstError = results.find((r) => r.status === "rejected");
      if (firstError && results.every((r) => r.status === "rejected")) {
        setError((firstError as PromiseRejectedResult).reason?.message ?? "Erro");
      }
      setLoading(false);
    });
  }, []);

  // Estoque crítico: soma dos lotes <= estoque mínimo
  const critical = ingredients.filter(
    (ing) => parseFloat(ing.total_quantity) <= parseFloat(ing.min_stock)
  );
  const expirationItems = alerts ? [...alerts.expired, ...alerts.expiring_soon] : [];

  if (loading) return <p className="text-muted-foreground">Carregando...</p>;
  if (error) return <p className="text-destructive">Erro ao carregar: {error}</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Cards de resumo */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Ingredientes cadastrados</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{ingredients.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Itens em estoque crítico</CardTitle>
            <TrendingDown className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-destructive">{critical.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Valor em risco (validade)</CardTitle>
            <CalendarClock className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              R$ {alerts ? parseFloat(alerts.total_value_at_risk).toFixed(2) : "--"}
            </p>
            <p className="text-xs text-muted-foreground">
              {alerts
                ? `${alerts.expired.length} vencido(s), ${alerts.expiring_soon.length} a vencer em ${alerts.days_window} dias`
                : "sem dados"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">WhatsApp (Z-API)</CardTitle>
            <Smartphone className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {zapi?.connected ? (
              <>
                <Badge className="bg-green-600 text-white hover:bg-green-600">Conectado</Badge>
                <p className="mt-1 text-xs text-muted-foreground">
                  {zapi.phone_number ?? "número não informado"}
                </p>
              </>
            ) : (
              <>
                <Badge variant="destructive">Desconectado</Badge>
                <p className="mt-1 text-xs text-muted-foreground">
                  {zapi?.status_message ?? "sem resposta"}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Alertas de vencimento */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="h-5 w-5 text-destructive" />
            Vencimentos (vencidos e próximos {alerts?.days_window ?? 7} dias)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {expirationItems.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum lote vencido ou próximo do vencimento. 🎉
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ingrediente</TableHead>
                  <TableHead>Fornecedor / Lote</TableHead>
                  <TableHead>Validade</TableHead>
                  <TableHead>Qtd. parada</TableHead>
                  <TableHead>R$ em risco</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expirationItems.map((item) => (
                  <TableRow key={item.lot_id}>
                    <TableCell className="font-medium">{item.ingredient_name}</TableCell>
                    <TableCell>
                      {item.supplier_brand}
                      {item.batch_number ? ` — ${item.batch_number}` : ""}
                    </TableCell>
                    <TableCell>
                      {new Date(`${item.expiration_date}T00:00:00`).toLocaleDateString("pt-BR")}
                    </TableCell>
                    <TableCell>
                      {item.quantity} {item.unit}
                    </TableCell>
                    <TableCell>R$ {parseFloat(item.value_at_risk).toFixed(2)}</TableCell>
                    <TableCell>
                      {item.status === "vencido" ? (
                        <Badge variant="destructive">
                          Vencido há {Math.abs(item.days_to_expiration)}d
                        </Badge>
                      ) : (
                        <Badge className="bg-amber-500 text-white hover:bg-amber-500">
                          Vence em {item.days_to_expiration}d
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Tabela de estoque crítico */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Estoque Crítico
          </CardTitle>
        </CardHeader>
        <CardContent>
          {critical.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum ingrediente abaixo do estoque mínimo. 🎉
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ingrediente</TableHead>
                  <TableHead>Estoque atual</TableHead>
                  <TableHead>Estoque mínimo</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {critical.map((ing) => (
                  <TableRow key={ing.id}>
                    <TableCell className="font-medium">{ing.name}</TableCell>
                    <TableCell>
                      {ing.total_quantity} {ing.unit}
                    </TableCell>
                    <TableCell>
                      {ing.min_stock} {ing.unit}
                    </TableCell>
                    <TableCell>
                      <Badge variant="destructive">Repor</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
