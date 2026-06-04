import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCollection } from "../../services/dataService.js";
import { compareLotIds } from "./naturalSort.js";
import ViticulturaIcon from "../../assets/icons/ViticulturaIcon.svg?react";
import VinificacionIcon from "../../assets/icons/VinificacionIcon.svg?react";
import EmbotelladoIcon from "../../assets/icons/EmbotelladoIcon.svg?react";
import SearchIcon from "../../assets/icons/SearchIcon.svg?react";
import "./Trazabilidad.css";

// The four collections that make up the vineyard → bottle paper trail.
const SOURCES = [
  ["viticultura", "Viticultura"],
  ["vinificacion", "Vinificación"],
  ["embotellado", "Embotellado"],
  ["trazabilidad", "Trazabilidad"],
];

const FILTERS = ["Todos", ...SOURCES.map(([, label]) => label)];

const COLLECTION_ICON = {
  Viticultura: ViticulturaIcon,
  Vinificación: VinificacionIcon,
  Embotellado: EmbotelladoIcon,
  Trazabilidad: SearchIcon,
};

// Fixtures use Date; Firestore uses Timestamp. Normalize both to a Date.
function toDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  if (typeof value.toDate === "function") return value.toDate();
  if (typeof value.seconds === "number") return new Date(value.seconds * 1000);
  return null;
}

function formatDateTime(value) {
  const date = toDate(value);
  if (!date) return "";
  const dd = String(date.getDate()).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `El ${dd}/${mm}/${date.getFullYear()} a las ${hh}:${min}`;
}

function StatusLabel({ estado }) {
  const ok = estado === "finalizado";
  return (
    <span className="status">
      <span className={`status-dot ${ok ? "green" : "yellow"}`} />
      {ok ? "Finalizado" : "En proceso"}
    </span>
  );
}

function RecentCard({ doc, onOpen }) {
  const ok = doc.estado === "finalizado";
  return (
    <article className="doc-card" onClick={onOpen}>
      <span className={`status-dot ${ok ? "green" : "yellow"}`} />
      <div className="doc-card-body">
        <span className="doc-card-id">{doc.id}</span>
        <span className="doc-card-author">{doc.creador}</span>
        <span className="doc-card-date">{formatDateTime(doc.fecha_creacion)}</span>
      </div>
    </article>
  );
}

const COLUMNS = [
  { key: "id", label: "Código" },
  { key: "creador", label: "Creado por" },
  { key: "estado", label: "Estado" },
  { key: "modificador", label: "Modificado por" },
];

export default function Trazabilidad() {
  const navigate = useNavigate();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("Todos");
  const [sort, setSort] = useState({ column: "fecha_creacion", dir: "desc" });

  const open = (id) => navigate(`/trazabilidad/${id}`);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const results = await Promise.all(SOURCES.map(([name]) => getCollection(name)));
        if (!active) return;
        const combined = results.flatMap((rows, i) =>
          rows.map((doc) => ({ ...doc, coleccion: SOURCES[i][1] }))
        );
        setDocs(combined);
      } catch (err) {
        if (active) setError("No se pudieron cargar los datos de trazabilidad.");
        console.error(err);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const recent = useMemo(
    () =>
      [...docs]
        .sort((a, b) => toDate(b.fecha_creacion) - toDate(a.fecha_creacion))
        .slice(0, 4),
    [docs]
  );

  const rows = useMemo(() => {
    const filtered = docs.filter((doc) => filter === "Todos" || doc.coleccion === filter);
    const dir = sort.dir === "asc" ? 1 : -1;
    return filtered.sort((a, b) => {
      switch (sort.column) {
        case "id":
          // Composite codes (VIT1MALC000724) sort naturally, not lexically.
          return dir * compareLotIds(a.id, b.id);
        case "creador":
        case "estado":
        case "modificador":
          return dir * (a[sort.column] || "").localeCompare(b[sort.column] || "");
        default:
          return dir * (toDate(a.fecha_creacion) - toDate(b.fecha_creacion));
      }
    });
  }, [docs, filter, sort]);

  const toggleSort = (column) =>
    setSort((prev) =>
      prev.column === column
        ? { column, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { column, dir: "asc" }
    );

  if (loading) return <div className="trz-state">Cargando trazabilidad…</div>;
  if (error) return <div className="trz-state error">{error}</div>;

  return (
    <div className="trz">
      <header className="trz-head">
        <h1 className="page-title">Trazabilidad</h1>
        <p className="page-sub">Cadena de custodia del viñedo a la botella.</p>
      </header>

      <section className="trz-section">
        <h2 className="section-title">Recientes</h2>
        <div className="trz-recent-grid">
          {recent.map((doc) => (
            <RecentCard key={`${doc.coleccion}-${doc.id}`} doc={doc} onOpen={() => open(doc.id)} />
          ))}
        </div>
      </section>

      <section className="trz-section">
        <div className="trz-controls">
          <h2 className="section-title">Archivos</h2>
          <label className="trz-filter">
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              {FILTERS.map((f) => (
                <option key={f} value={f}>
                  {f === "Todos" ? "Filtrar por" : f}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="trz-table">
          <div className="trz-row trz-row-head">
            {COLUMNS.map((col) => (
              <button
                key={col.key}
                className={`trz-th ${sort.column === col.key ? "active" : ""}`}
                onClick={() => toggleSort(col.key)}
              >
                {col.label}
                {sort.column === col.key && <span className={`trz-arrow ${sort.dir}`} />}
              </button>
            ))}
          </div>

          {rows.map((doc) => {
            const Icon = COLLECTION_ICON[doc.coleccion];
            return (
              <div
                className="trz-row clickable"
                key={`${doc.coleccion}-${doc.id}`}
                onClick={() => open(doc.id)}
              >
                <span className="trz-cell id">
                  {Icon && <Icon className="trz-col-icon" />}
                  {doc.id}
                </span>
                <span className="trz-cell stack">
                  <strong>{doc.creador || "—"}</strong>
                  <em>{formatDateTime(doc.fecha_creacion)}</em>
                </span>
                <span className="trz-cell">
                  <StatusLabel estado={doc.estado} />
                </span>
                <span className="trz-cell stack">
                  {doc.modificador ? (
                    <>
                      <strong>{doc.modificador}</strong>
                      <em>{formatDateTime(doc.fecha_modificacion)}</em>
                    </>
                  ) : (
                    "—"
                  )}
                </span>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
