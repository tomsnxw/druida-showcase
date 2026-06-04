// ──────────────────────────────────────────────────────────────────────────
// Pure aggregation over the sales collection.
//
// All the analytics maths lives here, separate from rendering: given the raw
// `ventas` documents it returns KPIs, a daily revenue series and ranked tops.
// Keeping it pure means the dashboard component is just presentation, and these
// reducers can be unit-tested without React or Chart.js in the room.
// ──────────────────────────────────────────────────────────────────────────

function toDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  if (typeof value.toDate === "function") return value.toDate();
  if (typeof value.seconds === "number") return new Date(value.seconds * 1000);
  return null;
}

const dayKey = (date) => date.toISOString().slice(0, 10);

export function summarize(ventas) {
  const revenue = ventas.reduce((sum, v) => sum + (v.totalFinal || 0), 0);
  const count = ventas.length;
  return {
    revenue,
    count,
    avgTicket: count ? Math.round(revenue / count) : 0,
  };
}

/** Revenue per day across the window, zero-filled so the line has no gaps. */
export function dailyRevenue(ventas, days = 60) {
  const byDay = new Map();
  for (const v of ventas) {
    const date = toDate(v.fechaVenta);
    if (!date) continue;
    const key = dayKey(date);
    byDay.set(key, (byDay.get(key) || 0) + (v.totalFinal || 0));
  }

  const series = [];
  const cursor = new Date();
  cursor.setHours(12, 0, 0, 0);
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(cursor);
    d.setDate(cursor.getDate() - i);
    series.push({ date: d, total: byDay.get(dayKey(d)) || 0 });
  }
  return series;
}

/** Top products by accumulated revenue. */
export function topProductos(ventas, limit = 5) {
  const totals = new Map();
  for (const v of ventas) {
    for (const item of v.productosVendidos || []) {
      const value = (item.precioUnidad || 0) * (item.cantidad || 0);
      totals.set(item.nombreProducto, (totals.get(item.nombreProducto) || 0) + value);
    }
  }
  return rank(totals, limit);
}

/** Top clients by accumulated revenue (display name resolved from the sale). */
export function topClientes(ventas, limit = 5) {
  const totals = new Map();
  const names = new Map();
  for (const v of ventas) {
    const c = v.cliente || {};
    const key = c.cuit || "—";
    const name = c.razonSocial || [c.nombre, c.apellido].filter(Boolean).join(" ") || key;
    names.set(key, name);
    totals.set(key, (totals.get(key) || 0) + (v.totalFinal || 0));
  }
  return rank(totals, limit).map((row) => ({ ...row, label: names.get(row.label) }));
}

function rank(totalsMap, limit) {
  return [...totalsMap.entries()]
    .map(([label, total]) => ({ label, total }))
    .sort((a, b) => b.total - a.total)
    .slice(0, limit);
}
