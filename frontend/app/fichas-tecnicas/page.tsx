"use client";

// Montagem da Ficha Técnica (BOM): quanto de cada ingrediente compõe 1 produto.
import { useEffect, useMemo, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { api, type Ingredient, type Product } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

// Linha editável da ficha técnica na tela
interface RecipeRow {
  ingredient_id: string;
  quantity: string;
}

export default function FichasTecnicasPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const [rows, setRows] = useState<RecipeRow[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Cadastro rápido de produto
  const [newProductName, setNewProductName] = useState("");
  const [newProductPrice, setNewProductPrice] = useState("0");

  useEffect(() => {
    Promise.all([api.listProducts(), api.listIngredients()])
      .then(([prods, ings]) => {
        setProducts(prods);
        setIngredients(ings);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const selectedProduct = useMemo(
    () => products.find((p) => p.id === selectedProductId) ?? null,
    [products, selectedProductId]
  );

  // Ao trocar de produto, carrega a ficha técnica existente nas linhas editáveis
  useEffect(() => {
    if (!selectedProduct) {
      setRows([]);
      return;
    }
    setRows(
      selectedProduct.recipe_items.map((item) => ({
        ingredient_id: item.ingredient_id,
        quantity: item.quantity,
      }))
    );
  }, [selectedProduct]);

  function updateRow(index: number, patch: Partial<RecipeRow>) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function handleCreateProduct() {
    if (!newProductName.trim()) return;
    setError(null);
    try {
      const created = await api.createProduct({
        name: newProductName,
        price: newProductPrice || "0",
      });
      setProducts((prev) => [...prev, created]);
      setSelectedProductId(created.id);
      setNewProductName("");
      setNewProductPrice("0");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleSaveRecipe() {
    if (!selectedProduct) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const valid = rows.filter((r) => r.ingredient_id && parseFloat(r.quantity) > 0);
      const updated = await api.saveRecipe(selectedProduct.id, valid);
      // Atualiza o produto na lista local com a ficha salva
      setProducts((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setMessage("Ficha técnica salva com sucesso!");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function unitOf(ingredientId: string): string {
    return ingredients.find((i) => i.id === ingredientId)?.unit ?? "";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Fichas Técnicas</h1>

      {/* Cadastro rápido de produto */}
      <Card>
        <CardHeader>
          <CardTitle>Novo produto</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="min-w-64 flex-1">
            <label className="mb-1 block text-sm font-medium">Nome do produto</label>
            <Input
              value={newProductName}
              onChange={(e) => setNewProductName(e.target.value)}
              placeholder="Ex: Pizza Calabresa"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Preço (R$)</label>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={newProductPrice}
              onChange={(e) => setNewProductPrice(e.target.value)}
              className="w-32"
            />
          </div>
          <Button onClick={handleCreateProduct}>
            <Plus className="h-4 w-4" /> Criar produto
          </Button>
        </CardContent>
      </Card>

      {/* Montagem da ficha técnica */}
      <Card>
        <CardHeader>
          <CardTitle>Montar ficha técnica</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-md">
            <label className="mb-1 block text-sm font-medium">Produto</label>
            <select
              value={selectedProductId}
              onChange={(e) => setSelectedProductId(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
            >
              <option value="">Selecione um produto...</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {selectedProduct && (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Ingrediente</TableHead>
                    <TableHead className="w-48">Quantidade por unidade</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <select
                          value={row.ingredient_id}
                          onChange={(e) => updateRow(index, { ingredient_id: e.target.value })}
                          className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                        >
                          <option value="">Selecione...</option>
                          {ingredients.map((ing) => (
                            <option key={ing.id} value={ing.id}>
                              {ing.name} ({ing.unit})
                            </option>
                          ))}
                        </select>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            step="0.001"
                            min="0"
                            value={row.quantity}
                            onChange={(e) => updateRow(index, { quantity: e.target.value })}
                          />
                          <span className="text-sm text-muted-foreground">
                            {unitOf(row.ingredient_id)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setRows((prev) => prev.filter((_, i) => i !== index))}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => setRows((prev) => [...prev, { ingredient_id: "", quantity: "0" }])}
                >
                  <Plus className="h-4 w-4" /> Adicionar ingrediente
                </Button>
                <Button onClick={handleSaveRecipe} disabled={saving}>
                  <Save className="h-4 w-4" />
                  {saving ? "Salvando..." : "Salvar ficha técnica"}
                </Button>
              </div>
            </>
          )}

          {message && <p className="text-sm text-green-600">{message}</p>}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
