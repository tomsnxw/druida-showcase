# Conversational data agent (backend)

The backend behind Druida's in-app assistant: a **Gemini agent that answers
natural-language questions about the winery by calling read-only Firestore
tools**. Ask *"¿cuál fue la venta más cara este mes?"* or *"¿de qué suelo viene
el Cabernet Franc 2023?"* and it figures out which tools to call, queries
Firestore, and answers in plain Spanish — grounded in real data, not guesses.

This is the **actual production code** ([`agent.py`](agent.py)), lightly tidied
(formatting + a module docstring), with secrets removed. The showcase web app
doesn't wire up the chat UI — running it needs a live Gemini key and Firestore —
so this folder is here to read, not to run in the demo.

## How it works

A single Flask service. The interesting part is the `/chat` flow:

```
user prompt ─▶ Gemini (gemini-2.5-pro) with system prompt + 16 tools
                  │
                  ├─ model asks to call tool(s)  ──▶ handle_tool_call()
                  │                                    runs the Firestore query
                  │   ◀── tool results (JSON) ────────┘
                  ▼
            (loop until no more tool calls)
                  │
                  ▼
            final answer ─▶ saved to the thread in Firestore ─▶ returned
```

The loop that drives tool use is deliberately simple:

```python
response = chat.send_message(user_prompt)
while response.function_calls:
    tool_responses = [handle_tool_call(call) for call in response.function_calls]
    response = chat.send_message(tool_responses)
```

### The tools (function calling)

Sixteen read-only query functions are registered in `AVAILABLE_FUNCTIONS` and
passed straight to Gemini, which calls them by name:

`consultar_ventas` · `consultar_clientes` · `consultar_proveedores` ·
`consultar_compras` · `consultar_ordenes_compra` · `consultar_stock` ·
`consultar_inventario` · `consultar_eventos` · `consultar_viticultura` ·
`consultar_vinificacion` · `consultar_embotellado` · `consultar_trazabilidad` ·
`consultar_vinos` · `consultar_archivos` · `consultar_documento_extremo`
(generic max/min over any collection) · `consultar_datos_usuario_activo`.

Each takes typed arguments (filters, ids, `contar=True` for counts, a
`campo_a_extraer` for single fields) and returns JSON. Gemini reads the
docstrings/signatures to decide which to call and how.

### The system prompt

A detailed persona ("Druida Digital" — hence the *"Consultando a los astros…"*
loading line) plus per-tool rules: which field means revenue vs. cost, how to
resolve an ambiguous document id across ventas/compras/órdenes, and **multi-hop
chains** — e.g. tracing a finished wine back to its grape's soil type walks
`vinos → trazabilidad → embotellado → vinificación → viticultura`.

### Threads

Each conversation is a document in the `historial_chat` Firestore collection.
History is loaded into the Gemini chat on first message of a session and saved
after each turn; a short title is generated once per thread with a cheaper model
(`gemini-2.5-flash`).

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/chat` | Send a message; returns the assistant's reply |
| `GET` | `/threads/<session_id>` | List a user's threads (paginated) |
| `GET` | `/history/<thread_id>` | Fetch a thread's messages |
| `DELETE` | `/history/<thread_id>` | Delete a thread |

## Running it (outside this showcase)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...      # read by genai.Client()
# place a Firestore service-account file at ./credentials.json (never commit it)
gunicorn --bind 0.0.0.0:8080 agent:app
```
