// ──────────────────────────────────────────────────────────────────────────
// Semantic lot codes + completeness state machine
//
// In Druida, every traceability document gets a *human-readable, self-describing
// ID* instead of an opaque UUID. A field worker reading `VIT1MAL C0007 24` can
// decode it on sight: Viticulture · own land · Malbec · Cuartel · 7th lot · 2024.
// This keeps the paper trail legible end-to-end (vineyard → tank → bottle) and
// makes the codes naturally sortable and groupable.
//
// These two pure functions are ports of the backend logic (Flask/Firestore) that
// originally assigned the codes and the document state. They're isolated here so
// the rule set is the single source of truth and is trivially unit-testable.
// ──────────────────────────────────────────────────────────────────────────

/**
 * Generate the 3-letter grape-variety code.
 *
 * Rules (in priority order):
 *  - "Cabernet X"  -> first 3 letters of X   ("Cabernet Sauvignon" -> SAU)
 *  - three words   -> initials of each        ("Petit Verdot Tinto" -> PVT)
 *  - two words     -> first initial + 2 chars ("Pinot Noir" -> PNO)
 *  - one word      -> first 3 letters         ("Malbec" -> MAL)
 */
export function grapeCode(variety) {
  const words = variety.trim().split(/\s+/);

  if (words[0].toLowerCase() === "cabernet" && words.length > 1) {
    return words[1].slice(0, 3).toUpperCase();
  }
  if (words.length === 3) {
    return (words[0][0] + words[1][0] + words[2][0]).toUpperCase();
  }
  if (words.length === 2) {
    return (words[0][0] + words[1].slice(0, 2)).toUpperCase();
  }
  if (words.length === 1 && variety.length >= 3) {
    return variety.slice(0, 3).toUpperCase();
  }
  return variety.toUpperCase();
}

const OWNERSHIP = { propia: "1", terceros: "2" };
const ORIGIN = { cuartel: "C", parcela: "P", hectarea: "HA", hilera: "H" };

/**
 * Build the composite lot id, e.g. VIT + 1 + MAL + C + 0007 + 24.
 * Origin is only encoded for own-land ("propia") lots.
 */
export function buildLotId({ ownership, variety, origin, counter, year }) {
  const own = OWNERSHIP[ownership] ?? "2";
  const grape = grapeCode(variety);
  const orig = ownership === "propia" ? ORIGIN[origin] ?? "" : "";
  const seq = String(counter).padStart(4, "0");
  const yy = String(year).slice(-2);
  return `VIT${own}${grape}${orig}${seq}${yy}`;
}

const ALLOWED_EMPTY = new Set([
  "provenienza",
  "nombre_empresa",
  "recipiente_tostado",
  "recipiente_uso",
  "nombre_bodega",
]);

/**
 * Derive a document's state from its completeness.
 *
 * A traceability record is "finalizado" only when every required field is filled;
 * any missing value (recursively, through nested objects and arrays) keeps it
 * "en proceso". Modelling state as a *function of the data* — rather than a flag
 * someone has to remember to flip — means it can never drift out of sync.
 */
export function deriveState(data) {
  for (const [key, value] of Object.entries(data)) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      if (Object.keys(value).length > 0 && deriveState(value) === "en proceso") {
        return "en proceso";
      }
    } else if (Array.isArray(value)) {
      for (const item of value) {
        if (item && typeof item === "object") {
          if (deriveState(item) === "en proceso") return "en proceso";
        } else if (item === null || (typeof item === "string" && item.trim() === "")) {
          return "en proceso";
        }
      }
    } else if (value === null || value === undefined) {
      return "en proceso";
    } else if (typeof value === "string" && value.trim() === "" && !ALLOWED_EMPTY.has(key)) {
      return "en proceso";
    }
  }
  return "finalizado";
}
