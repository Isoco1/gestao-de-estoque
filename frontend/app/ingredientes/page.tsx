"use client";

// Cadastro e listagem de Ingredientes + janela de detalhes com gestão de lotes.
import { useEffect, useState, type FormEvent } from "react";
import { PackagePlus, Plus, Trash2 } from "lucide-react";
import {
  api,
  type Ingredient,
  type IngredientLots,
  type MeasureUnit,
} from "@/lib/api";
import { daysUntil, expirationBadge, fmtDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const UNITS: { value: MeasureUnit; label: string }[] = [
  { value: "kg", label: "Quilograma (kg)" },
  { value: "g", label: "Grama (g)" },
  { value: "l", label: "Litro (l)" },
  { value: "ml", label: "Mililitro (ml)" },
  { value: "un", label: "Unidade (un)" },
];

/** Situação do lote para o badge da tabela de detalhes. */
function lotStatus(lot: { current_quantity: string; expiration_date: string | null }) {
  if (parseFloat(lot.current_quantity) <= 0) return { label: "Esgotado", variant: "secondary" as const };
  if (!lot.expiration_date) return { label: "Ativo", variant: "outline" as const };
  const days = daysUntil(lot.expiration_date);
  if (days <= 7) return expirationBadge(days);
  return { label: "Ativo", variant: "outline" as const };
}

export default function IngredientesPage() {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Campos do formulário de cadastro de ingrediente
  const [name, setName] = useState("");
  const [unit, setUnit] = useState<MeasureUnit>("g");
  const [stockQuantity, setStockQuantity] = useState("0");
  const [minStock, setMinStock] = useState("0");

  // Janela de detalhes (lotes)
  const [detail, setDetail] = useState<Ingredient | null>(null);
  const [lotsData, setLotsData] = useState<IngredientLots | null>(null);
  const [lotError, setLotError] = useState<string | null>(null);
  const [lotSaving, setLotSaving] = useState(false);

  // Campos do formulário de novo lote
  const [supplier, setSupplier] = useState("");
  const [batchNumber, setBatchNumber] = useState("");
  const [manufacturingDate, setManufacturingDate] = useState("");
  const [expirationDate, setExpirationDate] = useState("");
  const [lotQuantity, setLotQuantity] = useState("");
  const [lotCost, setLotCost] = useState("");

  const load = () =>
    api.listIngredients().then(setIngredients).catch((err: Error) => setError(err.message));

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createIngredient({
        name,
        unit,
        stock_quantity: stockQuantity,
        min_stock: minStock,
      });
      setName("");
      setStockQuantity("0");
      setMinStock("0");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string, name: string) {
    // Justificativa obrigatória: a API rejeita exclusões sem motivo (422)
    const reason = prompt(
      `Excluir "${name}"?\n\nInforme a justificativa da exclusão (mínimo 5 caracteres):`
    );
    if (reason === null) return; // usuário cancelou
    if (reason.trim().length < 5) {
      setError("A justificativa da exclusão precisa ter no mínimo 5 caracteres.");
      return;
    }
    try {
      setError(null);
      await api.deleteIngredient(id, reason.trim());
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function openDetail(ingredient: Ingredient) {
    setDetail(ingredient);
    setLotsData(null);
    setLotError(null);
    // Limpa o formulário de lote a cada abertura
    setSupplier("");
    setBatchNumber("");
    setManufacturingDate("");
    setExpirationDate("");
    setLotQuantity("");
    setLotCost("");
    try {
      setLotsData(await api.listLots(ingredient.id));
    } catch (err) {
      setLotError((err as Error).message);
    }
  }

  async function handleAddLot(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    setLotSaving(true);
    setLotError(null);
    try {
      await api.createLot(detail.id, {
        supplier_brand: supplier,
        batch_number: batchNumber || null,
        unit_cost: lotCost || "0",
        quantity: lotQuantity,
        manufacturing_date: manufacturingDate || null,
        expiration_date: expirationDate || null,
      });
      // Recarrega os lotes da janela e a listagem de totais atrás dela
      setLotsData(await api.listLots(detail.id));
      await load();
      setSupplier("");
      setBatchNumber("");
      setManufacturingDate("");
      setExpirationDate("");
      setLotQuantity("");
      setLotCost("");
    } catch (err) {
      setLotError((err as Error).message);
    } finally {
      setLotSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Ingredientes</h1>

      {/* Formulário de cadastro */}
      <Card>
        <CardHeader>
          <CardTitle>Novo ingrediente</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-5">
            <div className="md:col-span-2">
              <label className="mb-1 block text-sm font-medium">Nome</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex: Queijo Muçarela"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Unidade</label>
              <select
                value={unit}
                onChange={(e) => setUnit(e.target.value as MeasureUnit)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                {UNITS.map((u) => (
                  <option key={u.value} value={u.value}>
                    {u.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Qtd. inicial</label>
              <Input
                type="number"
                step="0.001"
                min="0"
                value={stockQuantity}
                onChange={(e) => setStockQuantity(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Estoque mínimo</label>
              <Input
                type="number"
                step="0.001"
                min="0"
                value={minStock}
                onChange={(e) => setMinStock(e.target.value)}
              />
            </div>
            <div className="flex items-end md:col-span-5">
              <Button type="submit" disabled={saving}>
                <Plus className="h-4 w-4" />
                {saving ? "Salvando..." : "Cadastrar"}
              </Button>
            </div>
          </form>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {/* Listagem */}
      <Card>
        <CardHeader>
          <CardTitle>Estoque atual</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Estoque</TableHead>
                <TableHead>Mínimo</TableHead>
                <TableHead>Situação</TableHead>
                <TableHead className="w-36" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {ingredients.map((ing) => {
                const isCritical =
                  parseFloat(ing.total_quantity) <= parseFloat(ing.min_stock);
                return (
                  <TableRow key={ing.id}>
                    <TableCell className="font-medium">{ing.name}</TableCell>
                    <TableCell>
                      {ing.total_quantity} {ing.unit}
                    </TableCell>
                    <TableCell>
                      {ing.min_stock} {ing.unit}
                    </TableCell>
                    <TableCell>
                      {isCritical ? (
                        <Badge variant="destructive">Crítico</Badge>
                      ) : (
                        <Badge variant="secondary">OK</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openDetail(ing)}
                        >
                          <PackagePlus className="h-4 w-4" /> Detalhes
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(ing.id, ing.name)}
                          title="Excluir (exige justificativa)"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Janela de detalhes: entrada de lote + lotes registrados */}
      <Dialog
        open={detail !== null}
        onClose={() => setDetail(null)}
        title={detail ? `${detail.name} — Lotes e Estoque` : ""}
      >
        {detail && (
          <div className="space-y-6">
            {/* Métricas consolidadas */}
            <div className="flex flex-wrap gap-6 rounded-md border bg-muted/50 p-4 text-sm">
              <div>
                <p className="text-muted-foreground">Estoque total</p>
                <p className="text-lg font-bold">
                  {lotsData ? lotsData.total_quantity : "..."} {detail.unit}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Custo médio ponderado</p>
                <p className="text-lg font-bold">
                  {lotsData?.weighted_average_cost
                    ? `R$ ${parseFloat(lotsData.weighted_average_cost).toFixed(4)} / ${detail.unit}`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Estoque mínimo</p>
                <p className="text-lg font-bold">
                  {detail.min_stock} {detail.unit}
                </p>
              </div>
            </div>

            {/* Formulário: adicionar estoque (novo lote) */}
            <div>
              <h3 className="mb-3 font-semibold">Adicionar estoque (novo lote)</h3>
              <form onSubmit={handleAddLot} className="grid gap-3 md:grid-cols-3">
                <div>
                  <label className="mb-1 block text-sm font-medium">Fornecedor / Marca *</label>
                  <Input
                    value={supplier}
                    onChange={(e) => setSupplier(e.target.value)}
                    placeholder="Ex: Laticínios Serra Azul"
                    required
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">Código do lote</label>
                  <Input
                    value={batchNumber}
                    onChange={(e) => setBatchNumber(e.target.value)}
                    placeholder="Ex: SA-778"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">
                    Peso / Quantidade ({detail.unit}) *
                  </label>
                  <Input
                    type="number"
                    step="0.001"
                    min="0.001"
                    value={lotQuantity}
                    onChange={(e) => setLotQuantity(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">Data de fabricação</label>
                  <Input
                    type="date"
                    value={manufacturingDate}
                    onChange={(e) => setManufacturingDate(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">Data de validade</label>
                  <Input
                    type="date"
                    value={expirationDate}
                    onChange={(e) => setExpirationDate(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">
                    Preço por {detail.unit} (R$)
                  </label>
                  <Input
                    type="number"
                    step="0.0001"
                    min="0"
                    value={lotCost}
                    onChange={(e) => setLotCost(e.target.value)}
                    placeholder="0.00"
                  />
                </div>
                <div className="flex items-end md:col-span-3">
                  <Button type="submit" disabled={lotSaving}>
                    <PackagePlus className="h-4 w-4" />
                    {lotSaving ? "Registrando..." : "Registrar entrada"}
                  </Button>
                </div>
              </form>
              {lotError && <p className="mt-2 text-sm text-destructive">{lotError}</p>}
            </div>

            {/* Lotes registrados */}
            <div>
              <h3 className="mb-3 font-semibold">Lotes registrados</h3>
              {!lotsData ? (
                <p className="text-sm text-muted-foreground">Carregando lotes...</p>
              ) : lotsData.lots.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nenhum lote registrado para este ingrediente.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Lote</TableHead>
                      <TableHead>Fornecedor</TableHead>
                      <TableHead>Fabricação</TableHead>
                      <TableHead>Validade</TableHead>
                      <TableHead>Saldo</TableHead>
                      <TableHead>Custo/{detail.unit}</TableHead>
                      <TableHead>Entrada</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {lotsData.lots.map((lot) => {
                      const status = lotStatus(lot);
                      return (
                        <TableRow
                          key={lot.id}
                          className={
                            parseFloat(lot.current_quantity) <= 0 ? "opacity-50" : undefined
                          }
                        >
                          <TableCell className="font-medium">
                            {lot.batch_number ?? "—"}
                          </TableCell>
                          <TableCell>{lot.supplier_brand}</TableCell>
                          <TableCell>{fmtDate(lot.manufacturing_date)}</TableCell>
                          <TableCell>{fmtDate(lot.expiration_date)}</TableCell>
                          <TableCell>
                            {lot.current_quantity} / {lot.initial_quantity} {detail.unit}
                          </TableCell>
                          <TableCell>
                            R$ {parseFloat(lot.unit_cost).toFixed(4)}
                          </TableCell>
                          <TableCell>
                            {new Date(lot.created_at).toLocaleDateString("pt-BR")}
                          </TableCell>
                          <TableCell>
                            <Badge variant={status.variant}>{status.label}</Badge>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
