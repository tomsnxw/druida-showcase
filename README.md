# Druida · Showcase

Three curated modules from **Druida**, a production ERP for a winery/vineyard
(inventory, sales, purchasing, events, weather, and grape-to-bottle
traceability). This repository is a self-contained slice of the front end, built
to **run fully offline against demo fixtures** — no Firebase, no backend, no
secrets.

```bash
npm install
npm run dev      # → http://localhost:5173
```

Everything you see is fed by synthetic data shaped exactly like the production
Firestore documents, so the UI and aggregation code run unchanged.

---

## What's inside

Druida is a large app; these pieces were chosen because each is **technically
interesting, self-contained, and shows a concrete design decision** rather than
boilerplate CRUD. The first three run live in the demo; the fourth is backend
code to read.

| Piece | What it shows |
| --- | --- |
| [Traceability](src/modules/trazabilidad) | Domain modelling: self-describing IDs, a derived state machine, natural-sort over composite codes |
| [Global fuzzy search](src/modules/busqueda) | The header search bar: normalizing nine heterogeneous collections into one fuzzy-searchable index |
| [Sales analytics](src/modules/estadisticas) | Pure aggregation reducers feeding a Chart.js dashboard |
| [Conversational agent](agent) | A Gemini agent with 16 Firestore function-calling tools (backend code) |

---

## 1 · Traceability — `src/modules/trazabilidad`

The chain of custody from vineyard to bottle: *viticultura → vinificación →
embotellado*, rolled up into a `trazabilidad` record.

**Self-describing IDs.** Every document gets a human-readable composite code
instead of an opaque UUID:

```
VIT 1 MAL C 0007 24
│   │ │   │ │    └─ year
│   │ │   │ └────── sequential counter
│   │ │   └──────── origin (Cuartel)
│   │ └──────────── grape variety (Malbec)
│   └────────────── ownership (own land)
└────────────────── stage (Viticulture)
```

A field worker can decode a lot on sight, and the codes group and sort naturally.
The encoding rules live as pure, testable functions in
[`loteCode.js`](src/modules/trazabilidad/loteCode.js) (`grapeCode`, `buildLotId`).

**State as a function of data.** A record is `finalizado` only when every required
field is filled; `deriveState()` walks the document recursively (through nested
objects and arrays) so the status can never drift out of sync with the content —
no flag for someone to forget to flip.

**Natural sort.** Composite codes must order the way humans expect (2 before 10,
not lexically). [`naturalSort.js`](src/modules/trazabilidad/naturalSort.js) splits
each id into letter/number chunks and compares them piecewise.

**Chain reconstruction.** Clicking a record opens its detail
([`DocDetail.jsx`](src/modules/trazabilidad/DocDetail.jsx)). A `trazabilidad`
rollup stores only references — which bottling run it produced and which
vinification batches fed it — so the view walks them to rebuild the whole story:
*batch → vinification → origin vineyard lot*, surfaced as tabs over the chain.
The walk is a pure function in [`chain.js`](src/modules/trazabilidad/chain.js).
This showcase is read-only; the production detail also edits and uploads label
artwork (Firebase Storage / backend), which is out of scope here.

> The pure functions here are JS ports of the original Flask/Firestore backend
> logic, isolated so the rule set is the single source of truth.

## 2 · Global fuzzy search — `src/modules/busqueda`

The search bar that lives in the top header
([`HeaderSearch.jsx`](src/modules/busqueda/HeaderSearch.jsx)): type and a
dropdown of matching documents appears. It spans **nine collections** that share
no schema — a wine lot, a client, an invoice, a stock line. Instead of
fuzzy-matching over `Object.keys(firstDoc)` (guessing fields from one arbitrary
document), each collection declares how to **project a document into a common
record** `{ id, collection, label, subtitle, date }` in
[`searchRecords.js`](src/modules/busqueda/searchRecords.js).

The payoff: [Fuse.js](https://www.fusejs.io/) indexes a uniform shape with
weighted fields, the dropdown renders identically for every type, and adding a
collection is one entry in a map.

## 3 · Sales analytics — `src/modules/estadisticas`

A faithful rebuild of the *Ventas* dashboard: a currency toggle (ARS / BNA /
CCL), two monthly/daily revenue line charts (overall and per-product), and four
ranked Top 5 lists (products, clients, events, members). All the maths is **pure
and isolated** in [`analytics.js`](src/modules/estadisticas/analytics.js)
(`monthlyRevenue`, `dailyRevenue`, `topProductos`, `topClientes`, `topEventos`,
`topMiembros`), so the component is only presentation and the reducers are
unit-testable without React in the room.

---

## 4 · Conversational data agent — `agent/`

The backend behind Druida's in-app assistant: a **Gemini agent that answers
questions about the winery by calling read-only Firestore tools**
([`agent.py`](agent/agent.py)). Ask *"¿cuál fue la venta más cara este mes?"* and
it picks the right tool, queries Firestore, and answers grounded in real data.

Highlights: a simple tool-calling loop (`while response.function_calls: …`),
**16 query tools** registered for Gemini function calling, multi-hop chains
(tracing a finished wine back to its grape's soil), and per-thread persistence
with auto-generated titles. This is the real production code, tidied and scrubbed
of secrets — see the [walkthrough](agent/README.md). The live demo above doesn't
wire up the chat UI (it needs a Gemini key and Firestore), so the agent is here
to read.

## The demo seam

The single design idea that makes this repo runnable with no secrets lives in
[`src/services/dataService.js`](src/services/dataService.js):

```js
export async function getCollection(name) {
  if (DEMO_MODE) return getDemoCollection(name);   // local fixtures
  // else: getDocs(collection(db, name))           // Firestore, in production
}
```

Every module reads through `getCollection(name)` and never imports Firebase
directly. Because the [fixtures](src/demo/fixtures) match the production document
shape 1:1, no `if (demo)` branches ever leak into the UI. Flip one constant and
the same code runs against live Firestore.

All names, codes, and figures in the fixtures are synthetic — there is no real
client or company data anywhere in this repository.

---

## Stack

React 19 · Vite · React Router · Chart.js · Fuse.js. Hand-written CSS with a
small shared token set in [`src/styles/base.css`](src/styles/base.css) — no UI
framework.

## Screenshots

| Traceability | Search | Analytics |
| --- | --- | --- |
| ![Traceability](docs/screenshots/trazabilidad.png) | ![Search](docs/screenshots/busqueda.png) | ![Analytics](docs/screenshots/estadisticas.png) |
