// ──────────────────────────────────────────────────────────────────────────
// Demo fixtures — shaped exactly like the Firestore documents they stand in for.
//
// The document shapes mirror production 1:1, including the *references* that let
// a `trazabilidad` rollup reconstruct its whole chain:
//
//   trazabilidad ──embotellado_id──▶ embotellado
//        └─partidas_usadas[].ref──▶ vinificacion ──lote_origen_ref──▶ viticultura
//
// so the detail view resolves the same way it does against live data. Dates are
// plain Date objects (creation/modification) or "YYYY-MM-DD" strings (the
// agronomic dates the original stores as text); the UI normalizes both.
//
// All names/codes are synthetic — no real client or company data.
// ──────────────────────────────────────────────────────────────────────────

const d = (s) => new Date(s);

export const viticultura = [
  {
    id: "VIT1MALC000724",
    coleccion: "Viticultura",
    creador: "Ana Duarte",
    fecha_creacion: d("2024-03-12T09:20:00"),
    modificador: "Ana Duarte",
    fecha_modificacion: d("2024-03-14T16:05:00"),
    estado: "finalizado",
    pertenencia: "propia",
    provenienza: "cuartel",
    variedad_uva: "Malbec",
    tipo_suelo: "Franco arcilloso",
    tipo_riego: "Goteo",
    altura_snm: 1050,
    fecha_primera_poda: "2023-07-15",
    fecha_segunda_poda: "2023-08-20",
    fecha_cosecha: "2024-03-08",
    nivel_acido: 5.4,
    nivel_azucar: 24.6,
    nivel_ph: 3.65,
    quintales: 142,
    dias_sol: 295,
    precipitacion_media_anual: 240,
    temperatura_media_anual: 16,
    humedad_media_anual: 55,
    precioUnidad: 38000,
  },
  {
    id: "VIT1SAUP000324",
    coleccion: "Viticultura",
    creador: "Bruno Sosa",
    fecha_creacion: d("2024-03-18T08:10:00"),
    modificador: "Ana Duarte",
    fecha_modificacion: d("2024-03-20T11:40:00"),
    estado: "finalizado",
    pertenencia: "propia",
    provenienza: "parcela",
    variedad_uva: "Cabernet Sauvignon",
    tipo_suelo: "Pedregoso",
    tipo_riego: "Goteo",
    altura_snm: 1180,
    fecha_primera_poda: "2023-07-18",
    fecha_segunda_poda: "2023-08-24",
    fecha_cosecha: "2024-03-15",
    nivel_acido: 5.9,
    nivel_azucar: 23.8,
    nivel_ph: 3.58,
    quintales: 98,
    dias_sol: 300,
    precipitacion_media_anual: 230,
    temperatura_media_anual: 15,
    humedad_media_anual: 52,
    precioUnidad: 42000,
  },
  {
    id: "VIT2BON000124",
    coleccion: "Viticultura",
    creador: "Bruno Sosa",
    fecha_creacion: d("2024-04-02T07:55:00"),
    modificador: "",
    fecha_modificacion: null,
    estado: "en proceso",
    pertenencia: "tercero",
    provenienza: "",
    nombre_finca: "Finca El Algarrobo",
    variedad_uva: "Bonarda",
    tipo_suelo: "Arenoso",
    tipo_riego: "Inundación",
    altura_snm: 780,
    fecha_cosecha: "2024-03-28",
    nivel_azucar: 22.1,
    quintales: 76,
    precioUnidad: 26000,
  },
];

export const vinificacion = [
  {
    id: "VIN1MALC000724",
    coleccion: "Vinificacion",
    creador: "Ana Duarte",
    fecha_creacion: d("2024-04-22T10:30:00"),
    modificador: "Camila Ríos",
    fecha_modificacion: d("2024-08-01T09:15:00"),
    estado: "finalizado",
    profesional_responsable: "Camila Ríos",
    lote_origen_ref: "VIT1MALC000724",
    hectolitros_procesados: 110,
    hectolitros_presentes: 98,
    tipo_uso: "Marca propia",
    recipiente: "Tanque inox 12",
    levadura: "Saccharomyces cerevisiae EC-1118",
    temperatura: 26,
    graduacion: 14.2,
    fermentacion_primaria: { inicio: "2024-04-24" },
  },
  {
    id: "VIN1SAUP000324",
    coleccion: "Vinificacion",
    creador: "Camila Ríos",
    fecha_creacion: d("2024-04-28T14:00:00"),
    modificador: "Camila Ríos",
    fecha_modificacion: d("2024-08-03T10:05:00"),
    estado: "finalizado",
    profesional_responsable: "Camila Ríos",
    lote_origen_ref: "VIT1SAUP000324",
    hectolitros_procesados: 72,
    hectolitros_presentes: 64,
    tipo_uso: "Marca propia",
    recipiente: "Barrica roble francés 7",
    levadura: "Saccharomyces cerevisiae D254",
    temperatura: 25,
    graduacion: 13.8,
    fermentacion_primaria: { inicio: "2024-04-30" },
  },
];

export const embotellado = [
  {
    id: "EMB1MALC000724",
    coleccion: "Embotellado",
    creador: "Camila Ríos",
    fecha_creacion: d("2024-09-10T11:00:00"),
    modificador: "Ana Duarte",
    fecha_modificacion: d("2024-09-11T08:30:00"),
    estado: "finalizado",
    profesional_responsable: "Ana Duarte",
    tipo_vino: "Tinto",
    tipo_uso: "Marca propia",
    partidas_usadas: [
      { ref: "VIN1MALC000724", cantidad_hl: 98 },
      { ref: "VIN1SAUP000324", cantidad_hl: 64 },
    ],
    embotellados_detalle: [
      { forma_botella: "Bordelesa", medida_botella: "750ml", cantidad_botellas: 12800, tipo_corcho: "Natural 45mm" },
    ],
    estiba_inicio: "2024-09-10",
    estiba_final: "2025-03-10",
    dias_estiba: 181,
  },
];

// A "trazabilidad" record rolls up a full vineyard→bottle chain by reference.
export const trazabilidad = [
  {
    id: "TRZ-MALBEC-2024-01",
    coleccion: "Trazabilidad",
    creador: "Ana Duarte",
    fecha_creacion: d("2024-09-12T12:00:00"),
    modificador: "Ana Duarte",
    fecha_modificacion: d("2024-09-12T12:00:00"),
    estado: "finalizado",
    embotellado_id: "EMB1MALC000724",
    partidas_usadas: [
      { ref: "VIN1MALC000724", cantidad_hl: 98 },
      { ref: "VIN1SAUP000324", cantidad_hl: 64 },
    ],
  },
];
