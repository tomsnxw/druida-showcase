import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Fuse from "fuse.js";
import { getCollection } from "../../services/dataService.js";
import { toSearchRecord } from "./searchRecords.js";
import SearchIcon from "../../assets/icons/SearchIcon.svg?react";
import "./HeaderSearch.css";

// Every collection reachable from the global search box — same set the real
// Druida header indexes.
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

// Only the traceability collections have a detail page in this showcase.
const NAVIGABLE = new Set(["viticultura", "vinificacion", "embotellado", "trazabilidad"]);

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

export default function HeaderSearch() {
  const navigate = useNavigate();
  const containerRef = useRef(null);
  const [records, setRecords] = useState([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  // Build the unified index once: load every collection in parallel, project
  // each document into a common record, sort by recency for the empty state.
  useEffect(() => {
    let active = true;
    (async () => {
      const results = await Promise.all(COLLECTIONS.map((c) => getCollection(c)));
      if (!active) return;
      const flattened = results
        .flatMap((rows, i) => rows.map((doc) => toSearchRecord(doc, COLLECTIONS[i])))
        .sort((a, b) => (b.date?.getTime() ?? 0) - (a.date?.getTime() ?? 0));
      setRecords(flattened);
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

  // Close the dropdown when clicking outside.
  useEffect(() => {
    const onClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const select = (record) => {
    setOpen(false);
    if (NAVIGABLE.has(record.collection)) navigate(`/trazabilidad/${record.id}`);
  };

  return (
    <div className="hs" ref={containerRef}>
      <div className={`hs-field ${open ? "active" : ""}`}>
        <SearchIcon />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="¿Qué querés buscar?"
          aria-label="Buscar"
        />
        {query && (
          <button className="hs-clear" onClick={() => setQuery("")} aria-label="Limpiar">
            ×
          </button>
        )}
      </div>

      {open && (
        <div className="hs-dropdown">
          {results.length > 0 ? (
            results.map((r) => (
              <div
                key={`${r.collection}-${r.id}`}
                className={`hs-option ${NAVIGABLE.has(r.collection) ? "" : "inert"}`}
                onClick={() => select(r)}
              >
                {r.label}
              </div>
            ))
          ) : (
            <div className="hs-option hs-empty">No se encontraron resultados</div>
          )}
        </div>
      )}
    </div>
  );
}
