// ──────────────────────────────────────────────────────────────────────────
// The single seam between the UI and its data source.
//
// Every module reads through `getCollection(name)` and never imports Firebase
// directly. Flip DEMO_MODE and the whole app runs offline against fixtures with
// zero UI changes — which is exactly what makes this repo runnable with no
// secrets. In the real Druida app, the `else` branch calls Firestore's getDocs.
//
// The promise + tiny delay mimic a network round-trip so loading states (which
// are part of the real UX) actually render in the showcase.
// ──────────────────────────────────────────────────────────────────────────
import { getDemoCollection } from "../demo/demoDb.js";

export const DEMO_MODE = true;

const FAKE_LATENCY_MS = 220;

export async function getCollection(name) {
  if (DEMO_MODE) {
    await new Promise((r) => setTimeout(r, FAKE_LATENCY_MS));
    return getDemoCollection(name);
  }

  // Real backend (Druida production):
  //   const snap = await getDocs(collection(db, name));
  //   return snap.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
  throw new Error("Live Firestore is not wired in the showcase build.");
}
