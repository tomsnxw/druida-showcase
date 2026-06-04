// ──────────────────────────────────────────────────────────────────────────
// Normalizing heterogeneous documents into one search record.
//
// Druida's global search box spans nine very different Firestore collections:
// a wine lot, a client, an invoice and a purchase order share no schema. Rather
// than fuzzy-match over `Object.keys(firstDoc)` (which guesses fields from one
// arbitrary document), each collection declares how to project a document into a
// common { id, collection, label, subtitle, date } shape.
//
// The payoff: Fuse.js indexes a uniform record, the results list renders the
// same way for every type, and adding a collection is one entry in this map.
// ──────────────────────────────────────────────────────────────────────────

const personName = (doc) =>
  [doc.nombre, doc.apellido].filter(Boolean).join(" ").trim();

const PROJECTORS = {
  ventas: (d) => ({
    label: d.productosVendidos?.[0]?.nombreProducto ?? "Venta",
    subtitle: d.cliente?.razonSocial || personName(d.cliente ?? {}) || d.cliente?.cuit,
    date: d.fechaVenta,
    route: "/ventas",
  }),
  clientes: (d) => ({
    label: d.razonSocial || personName(d) || d.id,
    subtitle: d.cuit,
    date: null,
    route: `/clientes/${d.id}`,
  }),
  inventario: (d) => ({
    label: d.nombre,
    subtitle: d.categoria,
    date: d.fecha,
    route: `/inventario/${d.id}`,
  }),
  compras: (d) => ({
    label: d.proveedor,
    subtitle: `${d.id} · ${d.estado}`,
    date: d.fecha,
    route: "/compras",
  }),
  stock: (d) => ({
    label: d.nombre,
    subtitle: `${d.cantidadUnidades} ${d.tipoUnidad}`,
    date: null,
    route: "/stock",
  }),
};

// Viticultura / vinificación / embotellado / trazabilidad share a shape.
const traceProjector = (d) => ({
  label: d.id,
  subtitle: d.creador,
  date: d.fecha_creacion,
  route: `/trazabilidad/${d.id}`,
});
for (const c of ["viticultura", "vinificacion", "embotellado", "trazabilidad"]) {
  PROJECTORS[c] = traceProjector;
}

function toDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  if (typeof value.toDate === "function") return value.toDate();
  if (typeof value.seconds === "number") return new Date(value.seconds * 1000);
  return null;
}

/** Project one raw document into the common, fuzzy-searchable record. */
export function toSearchRecord(doc, collection) {
  const project = PROJECTORS[collection];
  const view = project ? project(doc) : { label: doc.id, subtitle: "", date: null };
  return {
    id: doc.id,
    collection,
    label: view.label || doc.id,
    subtitle: view.subtitle || "",
    route: view.route || `/${collection}/${doc.id}`,
    date: toDate(view.date),
    // A single string Fuse can weigh alongside the structured fields.
    haystack: [view.label, view.subtitle, doc.id, collection].filter(Boolean).join(" "),
  };
}
