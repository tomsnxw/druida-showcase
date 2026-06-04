// ──────────────────────────────────────────────────────────────────────────
// Inventory / purchases / stock fixtures.
//
// These exist mainly so the global fuzzy search has a heterogeneous set of
// collections to index — items, suppliers and stock lines all live in the same
// search box in Druida. Shapes mirror the production documents.
// ──────────────────────────────────────────────────────────────────────────

const d = (s) => new Date(s);

export const inventario = [
  { id: "INV-0001", collection: "inventario", nombre: "Corchos naturales 45mm", categoria: "Insumos", cantidad: 24000, fecha: d("2024-02-10") },
  { id: "INV-0002", collection: "inventario", nombre: "Botellas Borgoña 750ml", categoria: "Insumos", cantidad: 18600, fecha: d("2024-02-14") },
  { id: "INV-0003", collection: "inventario", nombre: "Etiquetas Imum Coeli", categoria: "Packaging", cantidad: 9200, fecha: d("2024-03-01") },
  { id: "INV-0004", collection: "inventario", nombre: "Barricas roble francés", categoria: "Equipamiento", cantidad: 36, fecha: d("2023-11-20") },
];

export const compras = [
  { id: "OC-0007", collection: "compras", proveedor: "Tonelería Cuyo", total: 5400000, fecha: d("2024-03-05"), estado: "recibida" },
  { id: "OC-0008", collection: "compras", proveedor: "Vidriería del Oeste", total: 2120000, fecha: d("2024-03-22"), estado: "pendiente" },
  { id: "OC-0009", collection: "compras", proveedor: "Insumos Enológicos SA", total: 870000, fecha: d("2024-04-04"), estado: "recibida" },
];

export const stock = [
  { id: "VIT1MALC000724", collection: "stock", nombre: "VIT1MALC000724", categoria: "Vinos y Frutas", cantidadUnidades: 142, tipoUnidad: "Quintales" },
  { id: "VIT1SAUP000324", collection: "stock", nombre: "VIT1SAUP000324", categoria: "Vinos y Frutas", cantidadUnidades: 98, tipoUnidad: "Quintales" },
  { id: "EMB1MALC000724", collection: "stock", nombre: "Malbec Reserva 2022", categoria: "Producto terminado", cantidadUnidades: 12800, tipoUnidad: "Botellas" },
];
