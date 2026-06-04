import { useEffect, useMemo, useState } from "react";
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { getCollection } from "../../services/dataService.js";
import { DOLAR } from "../../demo/fixtures/ventas.js";
import {
  dailyRevenue,
  monthlyRevenue,
  periodTotal,
  topClientes,
  topEventos,
  topMiembros,
  topProductos,
} from "./analytics.js";
import EstadisticasIcon from "../../assets/icons/EstadisticasIcon.svg?react";
import TrofeoIcon from "../../assets/icons/TrofeoIcon.svg?react";
import ClientesIcon from "../../assets/icons/ClientesIcon.svg?react";
import EventosIcon from "../../assets/icons/EventosIcon.svg?react";
import MiembrosIcon from "../../assets/icons/MiembrosIcon.svg?react";
import "./Estadisticas.css";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler);

const PERIODOS = [
  { value: "mensual", label: "Mensuales" },
  { value: "anual", label: "Anuales" },
];

const CURRENCIES = ["ARS", "BNA", "CCL"];

export default function Estadisticas() {
  const [ventas, setVentas] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [eventos, setEventos] = useState([]);
  const [moneda, setMoneda] = useState("ARS");
  const [periodoVentas, setPeriodoVentas] = useState("anual");
  const [periodoProducto, setPeriodoProducto] = useState("anual");
  const [producto, setProducto] = useState(null);

  useEffect(() => {
    let active = true;
    Promise.all([getCollection("ventas"), getCollection("clientes"), getCollection("eventos")]).then(
      ([v, c, e]) => {
        if (!active) return;
        setVentas(v);
        setClientes(c);
        setEventos(e);
      }
    );
    return () => {
      active = false;
    };
  }, []);

  const productos = useMemo(() => {
    if (!ventas) return [];
    return [...new Set(ventas.flatMap((v) => (v.productosVendidos || []).map((i) => i.nombreProducto)))];
  }, [ventas]);

  useEffect(() => {
    if (!producto && productos.length) setProducto(productos[0]);
  }, [productos, producto]);

  // Convert ARS amounts to the selected display currency.
  const convert = (ars) => {
    if (moneda === "BNA") return ars / DOLAR.oficial;
    if (moneda === "CCL") return ars / DOLAR.ccl;
    return ars;
  };
  const money = (ars) => {
    const prefix = moneda === "ARS" ? "$" : "US$";
    return `${prefix} ${Math.round(convert(ars)).toLocaleString("es-AR")}`;
  };
  const compact = (ars) => {
    const v = convert(ars);
    const prefix = moneda === "ARS" ? "$" : "US$";
    if (v >= 1_000_000) return `${prefix}${(v / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
    if (v >= 1000) return `${prefix}${(v / 1000).toFixed(1).replace(/\.0$/, "")}K`;
    return `${prefix}${Math.round(v)}`;
  };

  const seriesFor = (periodo, prod) =>
    !ventas
      ? []
      : periodo === "anual"
        ? monthlyRevenue(ventas, { months: 12, producto: prod })
        : dailyRevenue(ventas, { days: 30, producto: prod });

  const ventasSeries = useMemo(() => seriesFor(periodoVentas, null), [ventas, periodoVentas]);
  const productoSeries = useMemo(
    () => seriesFor(periodoProducto, producto),
    [ventas, periodoProducto, producto]
  );

  const tops = useMemo(
    () =>
      !ventas
        ? null
        : {
            productos: topProductos(ventas),
            clientes: topClientes(ventas),
            eventos: topEventos(eventos),
            miembros: topMiembros(clientes),
          },
    [ventas, clientes, eventos]
  );

  if (!ventas || !tops) return <div className="est-state">Calculando métricas…</div>;

  return (
    <div className="est">
      <h1 className="page-title est-title">Estadísticas</h1>

      <div className="page-scroll">
      <div className="formtitle-container">
        <div className="formicon-container">
          <EstadisticasIcon className="formicon" />
        </div>
        <h2 className="formtitle">Ventas</h2>
      </div>
      <hr className="est-divider" />

      <div className="currency-selector">
        <span>Valores expresados en:</span>
        {CURRENCIES.map((c) => (
          <button
            key={c}
            className={`currency-button ${moneda === c ? "active" : ""}`}
            onClick={() => setMoneda(c)}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="est-charts-row">
        <ChartCard
          title="Gráfico de ventas"
          total={money(periodTotal(ventasSeries))}
          series={ventasSeries}
          periodo={periodoVentas}
          onPeriodo={setPeriodoVentas}
          compact={compact}
          money={money}
        />

        <ChartCard
          title="Ventas por producto"
          total={money(periodTotal(productoSeries))}
          series={productoSeries}
          periodo={periodoProducto}
          onPeriodo={setPeriodoProducto}
          compact={compact}
          money={money}
          extraControl={
            <select
              className="est-select"
              value={producto ?? ""}
              onChange={(e) => setProducto(e.target.value)}
            >
              {productos.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          }
        />
      </div>

      <div className="top-lists-row">
        <TopList Icon={TrofeoIcon} title="Top 5 Productos" rows={tops.productos} money={money} />
        <TopList Icon={ClientesIcon} title="Top 5 Clientes" rows={tops.clientes} money={money} />
        <TopList Icon={EventosIcon} title="Top 5 Eventos" rows={tops.eventos} money={money} />
        <TopList Icon={MiembrosIcon} title="Top 5 Miembros" rows={tops.miembros} money={money} />
      </div>
      </div>
    </div>
  );
}

function ChartCard({ title, total, series, periodo, onPeriodo, compact, money, extraControl }) {
  const data = {
    labels: series.map((p) =>
      p.date.toLocaleDateString("es-AR", { month: "short", year: "numeric" })
    ),
    datasets: [
      {
        data: series.map((p) => p.total),
        borderColor: "#e53935",
        borderWidth: 2,
        tension: 0, // straight segments, like the original
        pointRadius: 1,
        pointBackgroundColor: "#e53935",
        pointBorderColor: "#e53935",
        pointHoverRadius: 2,
        fill: false, // no area fill
      },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#fff",
        titleColor: "#333",
        bodyColor: "#e53935",
        borderColor: "#e0e3e7",
        borderWidth: 1,
        padding: 10,
        displayColors: false,
        callbacks: { label: (item) => money(item.parsed.y) },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { maxTicksLimit: 12, color: "#9aa3b0", font: { size: 10 } } },
      y: {
        border: { display: false },
        grid: { color: "#f0f2f5" },
        ticks: { callback: (v) => compact(v), color: "#9aa3b0", font: { size: 10 } },
      },
    },
  };

  return (
    <div className="chart-container">
      <div className="chart-head">
        <h3 className="chart-subtitle">
          <EstadisticasIcon className="chart-subtitle-icon" /> {title}
        </h3>
        <div className="chart-controls">
          {extraControl}
          <select className="est-select" value={periodo} onChange={(e) => onPeriodo(e.target.value)}>
            {PERIODOS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="chart-total">Ventas totales del período: {total}</p>
      <div className="chart-canvas">
        <Line data={data} options={options} />
      </div>
    </div>
  );
}

function TopList({ Icon, title, rows, money }) {
  return (
    <div className="top-list">
      <div className="top-list-head">
        <Icon className="top-list-icon" />
        <h3 className="top-list-title">{title}</h3>
      </div>
      <ol className="top-list-items">
        {rows.map((row) => (
          <li key={row.id ?? row.nombre} className="top-list-item">
            <span className="item-value">{money(row.total)}</span>
            <span className="item-name">{row.nombre}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
