// ──────────────────────────────────────────────────────────────────────────
// Pure aggregation over the sales collection.
//
// All the analytics maths lives here, separate from rendering: monthly revenue
// series (optionally filtered to one product) and the ranked tops. Keeping it
// pure means the dashboard component is just presentation, and these reducers
// can be unit-tested without React or Chart.js in the room.
// ──────────────────────────────────────────────────────────────────────────

function toDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  if (typeof value.toDate === "function") return value.toDate();
  if (typeof value.seconds === "number") return new Date(value.seconds * 1000);
  return null;
}

const lineValue = (item) => (item.precioUnidad || 0) * (item.cantidad || 0);

/**
 * Revenue per month across the last `months`, zero-filled so the line has no
 * gaps. With `producto` set, only that product's lines count.
 */
export function monthlyRevenue(ventas, { months = 12, producto = null } = {}) {
  const byMonth = new Map();
  for (const v of ventas) {
    const date = toDate(v.fechaVenta);
    if (!date) continue;
    const value = producto
      ? (v.productosVendidos || [])
          .filter((i) => i.nombreProducto === producto)
          .reduce((sum, i) => sum + lineValue(i), 0)
      : v.totalFinal || 0;
    if (!value) continue;
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    byMonth.set(key, (byMonth.get(key) || 0) + value);
  }

  const series = [];
  const now = new Date();
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    series.push({ date: d, total: byMonth.get(`${d.getFullYear()}-${d.getMonth()}`) || 0 });
  }
  return series;
}

/** Revenue per day across the last `days` (the "Mensuales" view). */
export function dailyRevenue(ventas, { days = 30, producto = null } = {}) {
  const byDay = new Map();
  for (const v of ventas) {
    const date = toDate(v.fechaVenta);
    if (!date) continue;
    const value = producto
      ? (v.productosVendidos || [])
          .filter((i) => i.nombreProducto === producto)
          .reduce((sum, i) => sum + lineValue(i), 0)
      : v.totalFinal || 0;
    if (!value) continue;
    const key = date.toISOString().slice(0, 10);
    byDay.set(key, (byDay.get(key) || 0) + value);
  }

  const series = [];
  const cursor = new Date();
  cursor.setHours(12, 0, 0, 0);
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(cursor);
    d.setDate(cursor.getDate() - i);
    series.push({ date: d, total: byDay.get(d.toISOString().slice(0, 10)) || 0 });
  }
  return series;
}

export const periodTotal = (series) => series.reduce((sum, p) => sum + p.total, 0);

/** Top products by accumulated revenue. */
export function topProductos(ventas, limit = 5) {
  const totals = new Map();
  for (const v of ventas) {
    for (const item of v.productosVendidos || []) {
      totals.set(item.nombreProducto, (totals.get(item.nombreProducto) || 0) + lineValue(item));
    }
  }
  return rank(totals).slice(0, limit).map((r) => ({ nombre: r.label, total: r.total }));
}

/** Top clients by accumulated revenue in the dataset. */
export function topClientes(ventas, limit = 5) {
  const totals = new Map();
  const names = new Map();
  for (const v of ventas) {
    const c = v.cliente || {};
    const key = c.cuit || "—";
    names.set(key, c.razonSocial || [c.nombre, c.apellido].filter(Boolean).join(" ") || key);
    totals.set(key, (totals.get(key) || 0) + (v.totalFinal || 0));
  }
  return rank(totals)
    .slice(0, limit)
    .map((r) => ({ id: r.label, nombre: names.get(r.label), total: r.total }));
}

/** Top events by revenue. */
export function topEventos(eventos, limit = 5) {
  return [...eventos]
    .sort((a, b) => b.ingreso - a.ingreso)
    .slice(0, limit)
    .map((e) => ({ id: e.id, nombre: e.titulo, total: e.ingreso }));
}

/** Top members by lifetime spend (montoHistorico) — distinct from period sales. */
export function topMiembros(clientes, limit = 5) {
  return [...clientes]
    .sort((a, b) => (b.montoHistorico || 0) - (a.montoHistorico || 0))
    .slice(0, limit)
    .map((c) => ({
      id: c.id,
      nombre: c.razonSocial || [c.nombre, c.apellido].filter(Boolean).join(" ") || c.id,
      total: c.montoHistorico || 0,
    }));
}

function rank(totalsMap) {
  return [...totalsMap.entries()]
    .map(([label, total]) => ({ label, total }))
    .sort((a, b) => b.total - a.total);
}
