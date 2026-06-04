// ──────────────────────────────────────────────────────────────────────────
// In-memory "database" backing demo mode.
//
// Keyed by collection name so it presents the same surface as a Firestore read:
// give it a collection, get back an array of documents. Adding a fixture file
// and registering it here is all it takes to make a new collection browsable.
// ──────────────────────────────────────────────────────────────────────────
import {
  viticultura,
  vinificacion,
  embotellado,
  trazabilidad,
} from "./fixtures/trazabilidad.js";
import { ventas, clientes, eventos } from "./fixtures/ventas.js";
import { inventario, compras, stock } from "./fixtures/operaciones.js";

const collections = {
  viticultura,
  vinificacion,
  embotellado,
  trazabilidad,
  ventas,
  clientes,
  eventos,
  inventario,
  compras,
  stock,
};

export function getDemoCollection(name) {
  return collections[name] ?? [];
}
