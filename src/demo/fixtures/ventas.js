// ──────────────────────────────────────────────────────────────────────────
// Sales / clients / events fixtures.
//
// `ventas` is generated procedurally so the analytics module has a realistic,
// 60-day time series to chart: a gentle upward trend, weekend dips, and a
// weighted product/client mix that produces clean, organic-looking rankings.
// The generator shapes data so the *charts* look alive — the component code
// that aggregates it stays identical to production.
// ──────────────────────────────────────────────────────────────────────────

function daysAgo(n) {
  const date = new Date();
  date.setDate(date.getDate() - n);
  date.setHours(12, 0, 0, 0);
  return date;
}

// Index 0 appears most often, last appears least -> rankings descend organically.
function weighted(arr) {
  const seq = [];
  arr.forEach((_, i) => {
    for (let k = 0; k < arr.length - i; k++) seq.push(i);
  });
  return seq;
}

const productos = [
  { nombre: "Imum Coeli Extra Brut 2023", precio: 120000 },
  { nombre: "Malbec Reserva 2022", precio: 85000 },
  { nombre: "Cabernet Franc 2021", precio: 62000 },
  { nombre: "Bonarda Joven 2023", precio: 47000 },
  { nombre: "Rosado de Malbec 2024", precio: 38000 },
  { nombre: "Espumante Nature 2023", precio: 29000 },
];

const clientesPool = [
  { key: "30-71011222-3", nombre: "", apellido: "", razonSocial: "Grupo Andes S.A." },
  { key: "30-70222333-4", nombre: "", apellido: "", razonSocial: "Delta Distribuciones SRL" },
  { key: "27-28333444-5", nombre: "María", apellido: "Fernández", razonSocial: "" },
  { key: "20-31444555-6", nombre: "Carlos", apellido: "Gómez", razonSocial: "" },
  { key: "30-70555666-7", nombre: "", apellido: "", razonSocial: "Vinoteca Norte" },
  { key: "27-26666777-8", nombre: "Lucía", apellido: "Romero", razonSocial: "" },
];

function buildVentas() {
  const prodSeq = weighted(productos);
  const cliSeq = weighted(clientesPool);
  const out = [];
  let counter = 0;
  const DIAS = 60;

  for (let day = DIAS - 1; day >= 0; day--) {
    const date = daysAgo(day);
    const idx = DIAS - 1 - day;
    const dow = date.getDay();

    let nSales = 2 + Math.round((idx / (DIAS - 1)) * 2); // 2..4, trending up
    if (dow === 0 || dow === 6) nSales = Math.max(1, nSales - 1);

    for (let s = 0; s < nSales; s++) {
      const prod = productos[prodSeq[counter % prodSeq.length]];
      // Stride + offset so the client mix isn't locked to the product mix —
      // otherwise the "top products" and "top clients" totals come out identical.
      const cli = clientesPool[cliSeq[(counter * 7 + 3) % cliSeq.length]];
      const cantidad = 1 + (counter % 2);
      out.push({
        id: `V-${day}-${s}`,
        collection: "ventas",
        tipoVenta: "VENTA",
        fechaVenta: date,
        fecha: date,
        totalFinal: cantidad * prod.precio,
        cliente: {
          cuit: cli.key,
          nombre: cli.nombre,
          apellido: cli.apellido,
          razonSocial: cli.razonSocial,
        },
        productosVendidos: [
          { nombreProducto: prod.nombre, cantidad, precioUnidad: prod.precio, categoria: "productos" },
        ],
      });
      counter++;
    }
  }
  return out;
}

export const ventas = buildVentas();

export const productNames = productos.map((p) => p.nombre);

export const clientes = [
  { id: "30-71011222-3", cuit: "30-71011222-3", razonSocial: "Grupo Andes S.A.", nombre: "", apellido: "", montoHistorico: 8650000 },
  { id: "30-70222333-4", cuit: "30-70222333-4", razonSocial: "Delta Distribuciones SRL", nombre: "", apellido: "", montoHistorico: 6420000 },
  { id: "27-28333444-5", cuit: "27-28333444-5", razonSocial: "", nombre: "María", apellido: "Fernández", montoHistorico: 5310000 },
  { id: "20-31444555-6", cuit: "20-31444555-6", razonSocial: "", nombre: "Carlos", apellido: "Gómez", montoHistorico: 4180000 },
  { id: "30-70555666-7", cuit: "30-70555666-7", razonSocial: "Vinoteca Norte", nombre: "", apellido: "", montoHistorico: 3275000 },
  { id: "27-26666777-8", cuit: "27-26666777-8", razonSocial: "", nombre: "Lucía", apellido: "Romero", montoHistorico: 2540000 },
].map((c) => ({ ...c, collection: "clientes" }));

export const eventos = [
  { id: "E1", collection: "eventos", titulo: "Cata Vertical Malbec", ingreso: 4200000 },
  { id: "E2", collection: "eventos", titulo: "Degustación Espumantes", ingreso: 2750000 },
  { id: "E3", collection: "eventos", titulo: "Lanzamiento Imum Coeli", ingreso: 1980000 },
  { id: "E4", collection: "eventos", titulo: "Cena Maridaje", ingreso: 1450000 },
  { id: "E5", collection: "eventos", titulo: "Visita Guiada Premium", ingreso: 920000 },
];
