import { useEffect, useMemo, useRef, useState } from "react";
import Fuse from "fuse.js";
import { getCollection } from "../../services/dataService.js";
import { toSearchRecord } from "./searchRecords.js";
import "./Busqueda.css";

// Every collection reachable from the global search box.
const COLLECTIONS = [
  "viticultura",
  "vinificacion",
  "embotellado",
  "trazabilidad",
  "compras",
  "stock",
  "inventario",
  "clientes",
  "ventas",
];

const COLLECTION_LABELS = {
  viticultura: "Viticultura",
  vinificacion: "Vinificación",
  embotellado: "Embotellado",
  trazabilidad: "Trazabilidad",
  compras: "Compras",
  stock: "Stock",
  inventario: "Inventario",
  clientes: "Clientes",
  ventas: "Ventas",
};

// Fuse weighs structured fields above the catch-all haystack so a name match
// outranks an incidental substring elsewhere in the record.
const FUSE_OPTIONS = {
  includeScore: true,
  threshold: 0.35,
  ignoreLocation: true,
  keys: [
    { name: "label", weight: 0.5 },
    { name: "id", weight: 0.3 },
    { name: "subtitle", weight: 0.15 },
    { name: "haystack", weight: 0.05 },
  ],
};

const MAX_RESULTS = 8;

function formatDate(date) {
  if (!date) return "";
  return date.toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" });
}

export default function Busqueda() {
  const [records, setRecords] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const inputRef = useRef(null);

  // Build the unified index once: load every collection in parallel, project
  // each document into the common record, sort by recency for the empty state.
  useEffect(() => {
    let active = true;
    (async () => {
      const results = await Promise.all(COLLECTIONS.map((c) => getCollection(c)));
      if (!active) return;
      const flattened = results
        .flatMap((rows, i) => rows.map((doc) => toSearchRecord(doc, COLLECTIONS[i])))
        .sort((a, b) => (b.date?.getTime() ?? 0) - (a.date?.getTime() ?? 0));
      setRecords(flattened);
      setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, []);

  const fuse = useMemo(() => new Fuse(records, FUSE_OPTIONS), [records]);

  const results = useMemo(() => {
    const q = query.trim();
    if (!q) return records.slice(0, MAX_RESULTS); // recency-sorted "recents"
    return fuse.search(q).slice(0, MAX_RESULTS).map((r) => r.item);
  }, [query, fuse, records]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div className="search">
      <header className="search-head">
        <h1 className="page-title">Búsqueda global</h1>
        <p className="page-sub">
          Un solo buscador difuso sobre {COLLECTIONS.length} colecciones — lotes, partidas,
          clientes, ventas, stock y más.
        </p>
      </header>

      <div className="search-box">
        <SearchGlyph />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={loading ? "Indexando…" : "¿Qué querés buscar?"}
          disabled={loading}
        />
        {query && (
          <button className="search-clear" onClick={() => setQuery("")} aria-label="Limpiar">
            ×
          </button>
        )}
      </div>

      <div className="search-meta">
        {query ? `${results.length} resultado${results.length === 1 ? "" : "s"}` : "Recientes"}
        {!loading && <span className="search-count">{records.length} documentos indexados</span>}
      </div>

      <ul className="search-results">
        {results.map((r) => (
          <li className="search-result" key={`${r.collection}-${r.id}`}>
            <span className={`search-badge c-${r.collection}`}>
              {COLLECTION_LABELS[r.collection]}
            </span>
            <span className="search-main">
              <span className="search-label">{r.label}</span>
              {r.subtitle && <span className="search-subtitle">{r.subtitle}</span>}
            </span>
            <span className="search-id">{r.id}</span>
            <span className="search-date">{formatDate(r.date)}</span>
          </li>
        ))}
        {!loading && results.length === 0 && (
          <li className="search-empty">No se encontraron resultados para “{query}”.</li>
        )}
      </ul>
    </div>
  );
}

function SearchGlyph() {
  return (
    <svg className="search-glyph" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
      <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
