# Piirakkabotti – Bakery Chatbot

A FastAPI + vanilla JS chatbot for Raka's Kotileipomo. It serves a static chat widget (frontend/) and a JSON Q&A knowledge base (backend/knowledgebase) with lightweight retrieval and optional LLM grounding. Includes an Ecwid order launcher (opens your shop) and has direct Ecwid store ordering enabled via the backend APIs once credentials are configured.

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

### Database logging (Railway Postgres)

The backend can log all chat messages and feedback to Postgres. Set a database URL and it will automatically create a table and insert rows.

- Set `DATABASE_URL` (or `DB_URL`) to your Railway connection string.
  - Example: `postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require`
  - Legacy `postgres://…` is also accepted; the app normalizes it to `postgresql://…` for SQLAlchemy.
- On startup, the app creates a table if needed:
  - `chat_messages(id, session_id, role, message, source, match_score, created_at)`
  - `role` will be `user`, `assistant`, or `feedback`.
- The embedded feedback form POSTs to `/api/feedback` and is stored with `role='feedback'`.

Local dev quick start:

1) Put your connection string in `.env`:

```
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
```

2) Start the server and send a few messages; verify inserts in `chat_messages`.

### Hybrid training (admin teach + feedback queue)

- Set `ADMIN_KEY` in your environment. Only the person with this secret can teach the bot.
- Teaching in chat: send `/teach` in the chat to open a small admin form. Enter language, question, answer, and your admin key.
- The new Q&A is saved to Postgres (`kb_items`) and used immediately for answers.
- Feedback queue: the existing feedback form also stores entries in `feedback_queue` with `status='pending'`.
- Admin endpoints (require `x-admin-key: $ADMIN_KEY` header):
  - `POST /api/kb/add` {lang, question, answer}
  - `GET /api/kb/list`
  - `POST /api/kb/toggle` {id, enabled}
  - `GET /api/feedback_queue?status=pending&limit=100`
  - `POST /api/feedback/promote` {id, lang, question, answer} → creates KB item and marks feedback as promoted

On startup, enabled KB items are indexed for retrieval; answers are returned when confidence gates pass.

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

The chatbot shows an in‑chat button that opens your Ecwid shop (`ECWID_STORE_URL`) and, when `ECWID_STORE_ID` and `ECWID_API_TOKEN` are set, can submit pickup orders straight to Ecwid. The backend flow:

- Collects order details in‑chat (items + quantities, pickup date/time, name, phone/email).
- POSTs them to `/api/order`.
- Uses the Ecwid REST API to create an order with:
  - payment method: “Pay at pickup”
  - payment status: `AWAITING_PAYMENT`
  - shipping method: “Pickup”
- Returns the Ecwid confirmation number to the chat.

Map your Ecwid product IDs/SKUs to the names you expose in chat so the order payload matches your catalog.

## Deploy

This repo includes `nixpacks.toml` and a `Procfile` suitable for Railway/Render:

```
web: /app/venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port $PORT
```

On platforms that build images, ensure Python 3.10+ and install `backend/requirements.txt`.

## Testing

The repo uses Python's built‑in `unittest` (no extra deps).

- Run all tests

```
python -m unittest discover -s tests -p "test_*.py" -v
```

- Run a single module

```
python -m unittest tests.test_constraints -v
python -m unittest tests.test_order_validation -v
```

What’s covered
- `tests/test_constraints.py` – Pure unit test for Ecwid constraint inference (`backend/order_constraints.py`).
- `tests/test_order_validation.py` – Regression tests for `POST /api/order` using `FastAPI` TestClient. Tests patch `/api/order_constraints` so they do not hit Ecwid.

Notes
- Tests do not require network access or real Ecwid credentials.
- The app loads `.env` at import time, but tests don’t depend on any env vars.

Manual API checks (useful during dev)

```
# Health and readiness
curl -sS http://localhost:8000/api/health | python3 -m json.tool

# Ecwid‑derived constraints (min lead, max days, blackout dates)
curl -sS "http://localhost:8000/api/order_constraints?debug=1" | python3 -m json.tool

# Pickup hours used by the calendar (Thu/Fri/Sat in local time)
curl -sS http://localhost:8000/api/pickup_hours | python3 -m json.tool

# Create an order (example – replace productId/sku and use a valid pickup_time)
curl -sS -X POST http://localhost:8000/api/order \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"productId":123,"quantity":1}],"name":"Test","phone":"+358...","pickup_time":"2025-09-12T12:00"}'
```

Tip: generating a valid `pickup_time` (local ISO, future, within open hours)

```
python - <<'PY'
import json, datetime as dt, urllib.request
cons = json.load(urllib.request.urlopen('http://localhost:8000/api/order_constraints'))
lead = int(cons.get('min_lead_minutes', 720))
t = dt.datetime.now() + dt.timedelta(minutes=lead)
t = (t.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1))
print(t.strftime('%Y-%m-%dT%H:%M'))
PY
```

If Ecwid doesn’t expose your “custom days” yet, you can override via `.env` for development:

```
ECWID_MIN_LEAD_MINUTES=720   # 12h
ECWID_MAX_ORDER_DAYS=60      # days ahead
```

## License

Internal use – add a license of your choice if you plan to open source.
