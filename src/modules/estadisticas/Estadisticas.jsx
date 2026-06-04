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
import { dailyRevenue, summarize, topClientes, topProductos } from "./analytics.js";
import "./Estadisticas.css";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler);

const money = (n) =>
  n.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });

const compact = (n) =>
  "$" + n.toLocaleString("es-AR", { notation: "compact", maximumFractionDigits: 1 });

export default function Estadisticas() {
  const [ventas, setVentas] = useState(null);

  useEffect(() => {
    let active = true;
    getCollection("ventas").then((rows) => active && setVentas(rows));
    return () => {
      active = false;
    };
  }, []);

  const model = useMemo(() => {
    if (!ventas) return null;
    return {
      kpis: summarize(ventas),
      series: dailyRevenue(ventas),
      productos: topProductos(ventas),
      clientes: topClientes(ventas),
    };
  }, [ventas]);

  if (!model) return <div className="est-loading">Calculando métricas…</div>;

  const lineData = {
    labels: model.series.map((p) =>
      p.date.toLocaleDateString("es-AR", { day: "2-digit", month: "short" })
    ),
    datasets: [
      {
        data: model.series.map((p) => p.total),
        borderColor: "#e53935",
        borderWidth: 2,
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: true,
        backgroundColor: (ctx) => {
          const { ctx: c, chartArea } = ctx.chart;
          if (!chartArea) return "rgba(229,57,53,0.12)";
          const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          g.addColorStop(0, "rgba(229,57,53,0.20)");
          g.addColorStop(1, "rgba(229,57,53,0)");
          return g;
        },
      },
    ],
  };

  const lineOptions = {
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
      x: {
        grid: { display: false },
        ticks: { maxTicksLimit: 8, color: "#9aa3b0", font: { size: 11 } },
      },
      y: {
        border: { display: false },
        grid: { color: "#f0f2f5" },
        ticks: { callback: (v) => compact(v), color: "#9aa3b0", font: { size: 11 } },
      },
    },
  };

  return (
    <div className="est">
      <header className="est-head">
        <h1 className="page-title">Estadísticas de ventas</h1>
        <p className="page-sub">Últimos 60 días.</p>
      </header>

      <div className="est-kpis">
        <Kpi label="Facturación" value={money(model.kpis.revenue)} />
        <Kpi label="Ventas" value={model.kpis.count.toLocaleString("es-AR")} />
        <Kpi label="Ticket promedio" value={money(model.kpis.avgTicket)} />
      </div>

      <section className="est-card est-chart">
        <h2>Facturación diaria</h2>
        <div className="est-chart-canvas">
          <Line data={lineData} options={lineOptions} />
        </div>
      </section>

      <div className="est-ranks">
        <RankCard title="Top productos" icon="🏆" rows={model.productos} format={money} />
        <RankCard title="Top clientes" icon="👤" rows={model.clientes} format={money} />
      </div>
    </div>
  );
}

function Kpi({ label, value }) {
  return (
    <div className="est-card est-kpi">
      <span className="est-kpi-label">{label}</span>
      <span className="est-kpi-value">{value}</span>
    </div>
  );
}

function RankCard({ title, icon, rows, format }) {
  return (
    <section className="est-card est-rank">
      <h2 className="est-rank-title">
        <span className="est-rank-emoji">{icon}</span> {title}
      </h2>
      <ol>
        {rows.map((row, i) => (
          <li key={row.label}>
            <span className="est-rank-pos">{i + 1}</span>
            <span className="est-rank-body">
              <span className="est-rank-value">{format(row.total)}</span>
              <span className="est-rank-label">{row.label}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
