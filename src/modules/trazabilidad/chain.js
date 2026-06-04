// ──────────────────────────────────────────────────────────────────────────
// Reconstructing a traceability chain from its references.
//
// A `trazabilidad` document stores only ids: which bottling run it rolls up
// (`embotellado_id`) and which vinification batches fed it (`partidas_usadas`).
// This walks those references — batch → vinification → its origin vineyard lot —
// so the detail view can show the whole vineyard-to-bottle story from one record.
//
// Pure and side-effect free: hand it the doc plus the loaded collections and it
// returns a fully-resolved copy. The same walk runs against Firestore in prod.
// ──────────────────────────────────────────────────────────────────────────

export function resolveChain(doc, { viticultura, vinificacion, embotellado }) {
  if (!doc || doc.coleccion !== "Trazabilidad") return doc;

  const emb = embotellado.find((e) => e.id === doc.embotellado_id) || null;

  const partidas = (doc.partidas_usadas || []).map((partida) => {
    const detalles = vinificacion.find((v) => v.id === partida.ref) || null;
    const origen = detalles?.lote_origen_ref
      ? viticultura.find((vit) => vit.id === detalles.lote_origen_ref) || null
      : null;
    return { ...partida, detalles, viticultura: origen };
  });

  return { ...doc, embotellado: emb, partidas_usadas: partidas };
}
