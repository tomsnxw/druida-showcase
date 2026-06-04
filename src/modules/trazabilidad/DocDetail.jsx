import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getCollection } from "../../services/dataService.js";
import { resolveChain } from "./chain.js";
import ViticulturaIcon from "../../assets/icons/ViticulturaIcon.svg?react";
import VinificacionIcon from "../../assets/icons/VinificacionIcon.svg?react";
import EmbotelladoIcon from "../../assets/icons/EmbotelladoIcon.svg?react";
import SearchIcon from "../../assets/icons/SearchIcon.svg?react";
import "./DocDetail.css";

const SOURCES = ["viticultura", "vinificacion", "embotellado", "trazabilidad"];

// Read-only showcase: the real app also has an "Etiqueta" tab and edit actions,
// but those write to Firebase Storage / the backend, so we keep the chain tabs.
const TRAZ_TABS = [
  { id: "viticultura", label: "Viticultura" },
  { id: "vinificacion", label: "Vinificación" },
  { id: "embotellado", label: "Embotellado" },
];

const mostrar = (v) => (v !== null && v !== undefined && v !== "" ? v : "-");

// "YYYY-MM-DD" agronomic dates → dd/mm/yyyy.
function fechaCorta(value) {
  if (!value) return "-";
  const [y, m, d] = String(value).split("-");
  return y && m && d ? `${d}/${m}/${y}` : "-";
}

// Creation/modification timestamps (Date) → "El dd/mm/yyyy a las hh:mm".
function fechaLarga(value) {
  if (!value) return "-";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  const p = (n) => String(n).padStart(2, "0");
  return `El ${p(date.getDate())}/${p(date.getMonth() + 1)}/${date.getFullYear()} a las ${p(
    date.getHours()
  )}:${p(date.getMinutes())}`;
}

const fechaMercado = (value) =>
  value
    ? new Date(value).toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit", year: "numeric" })
    : "-";

function Field({ label, value, className }) {
  return (
    <>
      <label className="data-label">{label}</label>
      <p className={`data-p ${className || ""}`.trim()}>{value}</p>
    </>
  );
}

function DocHeader({ Icon, doc, showModified = true }) {
  return (
    <div className="doc-detail-header">
      <div className="header-column header-id">
        <div className="doc-icon-container">
          <Icon className="doc-icon" />
        </div>
        <p className="header-value doc-id">{mostrar(doc.id)}</p>
      </div>
      <div className="header-column">
        <label className="header-label">Creado por</label>
        <p className="header-value">{mostrar(doc.creador)}</p>
        <p className="header-value">{fechaLarga(doc.fecha_creacion)}</p>
      </div>
      <div className="header-column">
        {showModified && (
          <>
            <label className="header-label">Última modificación</label>
            <p className="header-value">{mostrar(doc.modificador)}</p>
            <p className="header-value">{fechaLarga(doc.fecha_modificacion)}</p>
          </>
        )}
      </div>
    </div>
  );
}

function ViticulturaFields({ vit }) {
  if (!vit) return <p className="data-p">Sin datos de viticultura.</p>;
  return (
    <div className="columns-container">
      <div className="data-column">
        <Field label="Tipo de propiedad" value={mostrar(vit.pertenencia)} className="cap" />
        {vit.pertenencia?.toLowerCase() === "propia" && (
          <Field
            label="Área de cosecha"
            value={vit.provenienza?.toLowerCase() === "hectarea" ? "Hectárea" : mostrar(vit.provenienza)}
            className="cap"
          />
        )}
        {vit.pertenencia?.toLowerCase() === "tercero" && (
          <Field label="Nombre de la finca" value={mostrar(vit.nombre_finca)} />
        )}
        <Field label="Tipo de suelo" value={mostrar(vit.tipo_suelo)} />
        <Field label="Tipo de riego" value={mostrar(vit.tipo_riego)} />
        <Field label="Altura sobre el nivel del mar" value={vit.altura_snm ? `${vit.altura_snm}m` : "-"} />
        <Field label="Fecha de primera poda" value={fechaCorta(vit.fecha_primera_poda)} />
        <Field label="Fecha de segunda poda" value={fechaCorta(vit.fecha_segunda_poda)} />
      </div>
      <div className="data-column">
        <Field label="Fecha de cosecha" value={fechaCorta(vit.fecha_cosecha)} />
        <Field label="Cepa" value={mostrar(vit.variedad_uva)} />
        <Field label="Nivel de acidéz" value={vit.nivel_acido ? `${vit.nivel_acido} g/L` : "-"} />
        <Field label="Nivel de azúcar" value={vit.nivel_azucar ? `${vit.nivel_azucar}° Brix` : "-"} />
        <Field label="Nivel de pH" value={mostrar(vit.nivel_ph)} />
        <Field label="Quintales" value={vit.quintales ? `${vit.quintales} q` : "-"} />
      </div>
      <div className="data-column">
        <Field label="Días de sol" value={vit.dias_sol ? `${vit.dias_sol} d` : "-"} />
        <Field
          label="Precipitación media anual"
          value={vit.precipitacion_media_anual ? `${vit.precipitacion_media_anual} mm` : "-"}
        />
        <Field
          label="Temperatura media anual"
          value={vit.temperatura_media_anual ? `${vit.temperatura_media_anual}° C` : "-"}
        />
        <Field
          label="Humedad media anual"
          value={vit.humedad_media_anual ? `${vit.humedad_media_anual}%` : "-"}
        />
        <Field
          label="Precio unitario"
          value={vit.precioUnidad ? `$ ${vit.precioUnidad.toLocaleString("es-AR")}` : "-"}
        />
      </div>
    </div>
  );
}

function VinificacionFields({ vin, onNavigate }) {
  if (!vin) return <p className="data-p">Sin datos de vinificación.</p>;
  return (
    <div className="columns-container">
      <div className="data-column">
        <Field label="Profesional responsable" value={mostrar(vin.profesional_responsable)} className="bold" />
        <label className="data-label">Lote de origen</label>
        <p className="data-p link" onClick={() => onNavigate(vin.lote_origen_ref)}>
          {mostrar(vin.lote_origen_ref)}
        </p>
        <Field
          label="Hectolitros procesados"
          value={vin.hectolitros_procesados ? `${vin.hectolitros_procesados} hl` : "-"}
        />
        <Field
          label="Hectolitros disponibles"
          value={vin.hectolitros_presentes ? `${vin.hectolitros_presentes} hl` : "-"}
        />
        <Field label="Tipo de uso" value={mostrar(vin.tipo_uso)} className="cap" />
        <Field label="Fecha de inicio" value={fechaCorta(vin.fermentacion_primaria?.inicio)} />
      </div>
      <div className="data-column">
        <Field label="Recipiente utilizado" value={mostrar(vin.recipiente)} />
        <Field label="Tipo de levadura" value={mostrar(vin.levadura)} />
        <Field label="Temperatura" value={vin.temperatura ? `${vin.temperatura}° C` : "-"} />
        <Field label="Graduación alcohólica" value={vin.graduacion ? `${vin.graduacion}%` : "-"} />
      </div>
    </div>
  );
}

function EmbotelladoFields({ emb, onNavigate, showId = false }) {
  if (!emb) return <p className="data-p">Sin datos de embotellado.</p>;
  const totalBotellas = (emb.embotellados_detalle || []).reduce(
    (sum, p) => sum + Number(p.cantidad_botellas || 0),
    0
  );
  return (
    <div className="columns-container">
      <div className="data-column">
        {showId && (
          <>
            <label className="data-label">Embotellado</label>
            <p className="data-p link" onClick={() => onNavigate(emb.id)}>
              {mostrar(emb.id)}
            </p>
          </>
        )}
        <Field label="Profesional responsable" value={mostrar(emb.profesional_responsable)} className="bold" />
        <Field label="Tipo de vino" value={mostrar(emb.tipo_vino)} className="cap" />
        <Field label="Tipo de uso" value={mostrar(emb.tipo_uso)} className="cap" />
        {(emb.partidas_usadas || []).map((p, i) => (
          <div key={i}>
            <hr className="data-hr" />
            <label className="data-label">Partida</label>
            <p className="data-p link" onClick={() => onNavigate(p.ref)}>
              {p.ref}
            </p>
            <Field label="Hectolitros usados" value={`${p.cantidad_hl} hl`} />
          </div>
        ))}
      </div>
      <div className="data-column">
        {(emb.embotellados_detalle || []).map((p, i) => (
          <div key={i}>
            {i > 0 && <hr className="data-hr" />}
            <Field label="Tipo de botella" value={p.forma_botella} />
            <Field label="Medida de la botella" value={p.medida_botella} />
            <Field label="Cantidad de botellas" value={Number(p.cantidad_botellas).toLocaleString("es-AR")} />
            <Field label="Tipo de corcho" value={p.tipo_corcho} />
          </div>
        ))}
      </div>
      <div className="data-column">
        <Field label="Fecha de embotellado" value={fechaMercado(emb.estiba_inicio)} />
        <Field label="Fecha de salida a mercado" value={fechaMercado(emb.estiba_final)} />
        <div className="gray-box">
          <label className="data-label">Días totales de estiba</label>
          <p className="data-p big">{emb.dias_estiba ? `${emb.dias_estiba}d` : "-"}</p>
        </div>
        <div className="gray-box">
          <label className="data-label">Total de botellas</label>
          <p className="data-p big">{totalBotellas.toLocaleString("es-AR")}</p>
        </div>
      </div>
    </div>
  );
}

export default function DocDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [collections, setCollections] = useState(null);
  const [activeTraz, setActiveTraz] = useState("viticultura");
  const [partidaIndex, setPartidaIndex] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      const [viticultura, vinificacion, embotellado, trazabilidad] = await Promise.all(
        SOURCES.map((name) => getCollection(name))
      );
      if (active) setCollections({ viticultura, vinificacion, embotellado, trazabilidad });
    })();
    return () => {
      active = false;
    };
  }, []);

  const doc = useMemo(() => {
    if (!collections) return undefined;
    const all = [
      ...collections.viticultura,
      ...collections.vinificacion,
      ...collections.embotellado,
      ...collections.trazabilidad,
    ];
    const found = all.find((d) => d.id === id);
    if (!found) return null;
    return found.coleccion === "Trazabilidad" ? resolveChain(found, collections) : found;
  }, [collections, id]);

  // Reset tab/partida state when navigating between documents.
  useEffect(() => {
    setActiveTraz("viticultura");
    setPartidaIndex(0);
  }, [id]);

  const goTo = (targetId) => targetId && navigate(`/trazabilidad/${targetId}`);

  if (doc === undefined) return <div className="dd-state">Cargando documento…</div>;
  if (doc === null) return <div className="dd-state">Documento no encontrado.</div>;

  const ICONS = {
    Viticultura: ViticulturaIcon,
    Vinificacion: VinificacionIcon,
    Embotellado: EmbotelladoIcon,
  };

  // ── Standalone document (single stage) ──────────────────────────────────
  if (doc.coleccion !== "Trazabilidad") {
    const Icon = ICONS[doc.coleccion] || SearchIcon;
    return (
      <div className="doc-detail">
        <h1 className="page-title">Trazabilidad</h1>
        <DocHeader Icon={Icon} doc={doc} showModified={Boolean(doc.modificador)} />
        {doc.coleccion === "Viticultura" && <ViticulturaFields vit={doc} />}
        {doc.coleccion === "Vinificacion" && <VinificacionFields vin={doc} onNavigate={goTo} />}
        {doc.coleccion === "Embotellado" && <EmbotelladoFields emb={doc} onNavigate={goTo} />}
      </div>
    );
  }

  // ── Trazabilidad rollup (full chain) ────────────────────────────────────
  const partida = doc.partidas_usadas?.[partidaIndex];
  const showPartidaSelector = doc.partidas_usadas?.length > 1 && activeTraz !== "embotellado";

  return (
    <div className="doc-detail">
      <h1 className="page-title">Trazabilidad</h1>
      <DocHeader Icon={SearchIcon} doc={doc} showModified={false} />

      <ul className="tabs-nav">
        {TRAZ_TABS.map((tab) => (
          <li key={tab.id} className={activeTraz === tab.id ? "active" : ""}>
            <a href="#" onClick={(e) => { e.preventDefault(); setActiveTraz(tab.id); }}>
              {tab.label}
            </a>
          </li>
        ))}
      </ul>

      {showPartidaSelector && (
        <div className="partida-selector">
          {doc.partidas_usadas.map((p, i) => (
            <button
              key={p.ref}
              className={i === partidaIndex ? "active" : ""}
              onClick={() => setPartidaIndex(i)}
            >
              {p.ref}
            </button>
          ))}
        </div>
      )}

      <div className="tab-content">
        {activeTraz === "viticultura" && <ViticulturaFields vit={partida?.viticultura} />}
        {activeTraz === "vinificacion" && <VinificacionFields vin={partida?.detalles} onNavigate={goTo} />}
        {activeTraz === "embotellado" && (
          <EmbotelladoFields emb={doc.embotellado} onNavigate={goTo} showId />
        )}
      </div>
    </div>
  );
}
