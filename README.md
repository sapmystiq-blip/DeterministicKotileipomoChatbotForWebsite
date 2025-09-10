# Piirakkabotti – Bakery Chatbot

A FastAPI + vanilla JS chatbot for Raka's Kotileipomo. It serves a static chat widget (frontend/) and a JSON Q&A knowledge base (backend/knowledgebase) with lightweight retrieval and optional LLM grounding. Includes an Ecwid order launcher (opens your shop) and is ready for programmatic Ecwid ordering via backend APIs.

## Quick Start

- Python 3.10+ recommended (3.8 works with `eval_type_backport`).
- Create venv and install deps:

```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt
# Python <3.10 only:
pip install eval_type_backport
```

- Run the app:

```
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

- Open http://localhost:8000

## Environment

These variables are optional unless noted.

- `PRIMARY_LANG` – default reply language (`fi` | `en` | `sv`). Default: `fi`.
- `LANGUAGE_POLICY` – `always_primary` or `match_user`. Default: `always_primary`.
- `OPENAI_API_KEY` – enables LLM grounding if set.
- `LLM_ENABLED` – `true`/`false`. When `false`, answers are KB only.
- `ECWID_STORE_URL` – URL to your online shop (used by the in‑chat “Order” button). Default: `https://rakaskotileipomo.fi/verkkokauppa`.
- (Planned) Programmatic Ecwid ordering:
  - `ECWID_STORE_ID` – numeric store ID.
  - `ECWID_API_TOKEN` – private API token with order scope. Must be kept server‑side only.

## Project Layout

- `frontend/` – `index.html`, `styles.css`, `chat.js` (floating bubble + widget UI)
- `backend/app.py` – FastAPI app, KB loader, retrieval, API routes
- `backend/knowledgebase/*.json` – Q&A entries (English/Finnish); loaded on startup
- `scripts/smoke_test.py` – local health + chat checks without opening a socket

## Knowledge Base

Each KB file is a list of objects:

```json
{"title":"Opening Hours","question":"What are your opening hours?","answer":"Thu–Fri 11–17, Sat 11–15."}
```

Add/modify JSON files under `backend/knowledgebase` and restart the app.

## Ordering via Ecwid

Today, the chatbot shows an in‑chat button that opens your Ecwid shop (`ECWID_STORE_URL`). Because Ecwid API tokens must be kept secret, any “order without opening the shop” flow needs to run on the server:

- Collect order details in‑chat (items + quantities, pickup date/time, name, phone/email).
- POST to a new backend endpoint (e.g. `/api/order`).
- Backend uses Ecwid REST API (store ID + API token) to create an order with:
  - payment method: “Pay at pickup”
  - payment status: `AWAITING_PAYMENT`
  - shipping method: “Pickup”
- Return an order confirmation number to the chat.

If you want this implemented, share your `ECWID_STORE_ID`, `ECWID_API_TOKEN`, and (ideally) a mapping of product IDs/SKUs to the names you want to expose in chat.

## Deploy

This repo includes `nixpacks.toml` and a `Procfile` suitable for Railway/Render:

```
web: /app/venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port $PORT
```

On platforms that build images, ensure Python 3.10+ and install `backend/requirements.txt`.

## License

Internal use – add a license of your choice if you plan to open source.

