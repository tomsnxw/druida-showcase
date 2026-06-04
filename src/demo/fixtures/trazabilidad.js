// ──────────────────────────────────────────────────────────────────────────
// Demo fixtures — shaped exactly like the Firestore documents they stand in for.
//
// Because the shape matches production 1:1, every component renders these the
// same way it renders live data: no `if (demo)` branches leak into the UI.
// Dates are plain Date objects; the data layer normalizes them so components
// never care whether a value came from a fixture or a Firestore Timestamp.
//
// All names/codes here are synthetic — no real client or company data.
// ──────────────────────────────────────────────────────────────────────────

const d = (s) => new Date(s);

export const viticultura = [
  {
    id: "VIT1MALC000724",
    creador: "Ana Duarte",
    fecha_creacion: d("2024-03-12T09:20:00"),
    pertenencia: "propia",
    provenienza: "cuartel",
    variedad_uva: "Malbec",
    quintales: 142,
    estado: "finalizado",
    modificador: "Ana Duarte",
    fecha_modificacion: d("2024-03-14T16:05:00"),
  },
  {
    id: "VIT1SAUP000324",
    creador: "Bruno Sosa",
    fecha_creacion: d("2024-03-18T08:10:00"),
    pertenencia: "propia",
    provenienza: "parcela",
    variedad_uva: "Cabernet Sauvignon",
    quintales: 98,
    estado: "finalizado",
    modificador: "Ana Duarte",
    fecha_modificacion: d("2024-03-20T11:40:00"),
  },
  {
    id: "VIT2BON000124",
    creador: "Bruno Sosa",
    fecha_creacion: d("2024-04-02T07:55:00"),
    pertenencia: "terceros",
    provenienza: "",
    variedad_uva: "Bonarda",
    quintales: 76,
    estado: "en proceso",
    modificador: "",
    fecha_modificacion: null,
  },
];

export const vinificacion = [
  {
    id: "VIN1MALC000724",
    creador: "Ana Duarte",
    fecha_creacion: d("2024-04-22T10:30:00"),
    lote_origen: "VIT1MALC000724",
    recipiente: "Tanque inox 12",
    litros: 9800,
    estado: "finalizado",
    modificador: "Camila Ríos",
    fecha_modificacion: d("2024-08-01T09:15:00"),
  },
  {
    id: "VIN1SAUP000324",
    creador: "Camila Ríos",
    fecha_creacion: d("2024-04-28T14:00:00"),
    lote_origen: "VIT1SAUP000324",
    recipiente: "Barrica roble 7",
    litros: 6400,
    estado: "en proceso",
    modificador: "",
    fecha_modificacion: null,
  },
];

export const embotellado = [
  {
    id: "EMB1MALC000724",
    creador: "Camila Ríos",
    fecha_creacion: d("2024-09-10T11:00:00"),
    partida_origen: "VIN1MALC000724",
    botellas: 12800,
    formato: "750ml",
    estado: "finalizado",
    modificador: "Ana Duarte",
    fecha_modificacion: d("2024-09-11T08:30:00"),
  },
];

// "trazabilidad" rolls up a full vineyard→bottle chain into one record.
export const trazabilidad = [
  {
    id: "TRZ-MALBEC-2024-01",
    creador: "Ana Duarte",
    fecha_creacion: d("2024-09-12T12:00:00"),
    cadena: ["VIT1MALC000724", "VIN1MALC000724", "EMB1MALC000724"],
    estado: "finalizado",
    modificador: "Ana Duarte",
    fecha_modificacion: d("2024-09-12T12:00:00"),
  },
];
