# Project Architecture (Overview)

This project implements a lightweight Q&A chatbot with optional in‑chat ordering backed by FastAPI and vanilla JS.

## High‑Level

- Frontend (vanilla JS)
  - Chat widget (`frontend/index.html`, `frontend/styles.css`, `frontend/chat.js`)
  - Ordering flow (being modularized):
    - `frontend/order/api.js` – HTTP helpers (categories, products, constraints, order)
    - `frontend/order/state.js` – in‑chat cart + checkout state (localStorage persistence)
    - `frontend/order/controller.js` – orchestrates the flow (WIP)

- Backend (FastAPI)
  - `backend/app.py` – app bootstrap, KB loading, chat endpoints, static serving
  - `backend/ecwid_client.py` – tiny Ecwid REST client
  - `backend/order_constraints.py` – pure logic to infer min lead, max window, blackout ranges
  - `backend/routers/orders.py` – v2 ordering endpoints (categories, products, constraints)
- `backend/knowledgebase/*.json` – Deterministic KB (hours, FAQ, allergens, product aliases)
  - Legacy JSON moved to `backend/knowledgebase/deprecated/` and no longer used by chat.

## Ordering Data Flow

1. Frontend asks backend for constraints
   - `GET /api/order_constraints` (v1) – in use today
   - `GET /api/v2/order_constraints` (new router; same data shape) – to migrate
   - Returns:
     - `min_lead_minutes` – minimum time from now to pickup (Ecwid → fulfillmentTimeInMinutes)
     - `max_days` – order‑ahead window (Ecwid → availabilityPeriod mapping or custom days when added)
     - `blackout_dates` – Ecwid blackout date ranges

2. Calendar UI renders available days
   - Disables past days, before lead window, after max window, and blackout ranges
   - Auto‑advances to first available month and preselects earliest available day

3. Time UI renders only full‑hour slots within pickup hours and ≥ lead time

4. Frontend posts an order
   - `POST /api/order` (v1) – server validates format + hours + lead + window + blackouts
   - On success, server calls Ecwid Orders API using store ID + private token

## Server‑Side Validation

- `pickup_time` is mandatory and must be `YYYY-MM-DDTHH:MM` local time.
- Opening hours are enforced (Thu/Fri 11–17, Sat 11–15 by default).
- Ecwid‑derived constraints are enforced at order time even if the UI was bypassed.
- Blackout ranges are enforced both in UI and backend.

## Ecwid Integration

- `backend/ecwid_client.py` centralizes API calls (`/products`, `/categories`, `/profile`, `/profile/shippingOptions`).
- `backend/order_constraints.py` reads Ecwid payloads:
  - Lead time: `fulfillmentTimeInMinutes`, `pickupPreparationTime(Hours|Minutes)`, etc.
  - Max days: `availabilityPeriod` mapping; and when Ecwid adds a custom numeric field, it will be preferred.
  - Blackouts: `blackoutDates`.

## Routing (current vs v2)

- v1 routes (existing in `app.py`):
  - `/api/health`, `/api/chat`, `/api/products`, `/api/categories`, `/api/order_constraints`, `/api/order`, `/api/pickup_hours`, `/api/check_pickup`.
- v2 routes (new router; non‑breaking):
  - `/api/v2/products`, `/api/v2/categories`, `/api/v2/order_constraints`.
- The app includes the v2 router so new clients can migrate endpoint‑by‑endpoint without breaking existing code.

## Tests

- `tests/test_constraints.py` – unit tests for constraints inference (pure function tests).
- `tests/test_order_validation.py` – regression tests for order validation (uses FastAPI TestClient and patches `/api/order_constraints`).
- `tests/test_intents.py` – intent router unit tests (hours/menu/allergens basic checks).

## Deterministic Knowledge Base (KB)

We scope the chatbot to bakery topics and answer deterministically without embeddings:

- `backend/knowledgebase/hours.json`: weekly hours + date exceptions (validated by `WeeklyHours`).
- `backend/knowledgebase/faq.json`: multilingual FAQ items (`FaqItem`).
- `backend/knowledgebase/allergens.json`: canonical allergen keys, synonyms, and localized disclaimers (`AllergenMap`).
- `backend/knowledgebase/product_aliases.json`: names/aliases used to recognize products in questions.
- `backend/knowledgebase/blackouts.json`: documentation stub; actual blackout ranges come live from Ecwid.

Validation models live in `backend/kb_models.py` and are used by `backend/intent_router.py`.

### Editing workflow

- Update JSON files and restart the server (hot‑reload in dev). The router validates on read and safely falls back when invalid.
- Prices and availability are fetched from Ecwid at answer time when credentials are configured.

### Chat flow

`/api/chat` runs:
- Rule‑based greetings/identity → deterministic intent router (`backend/intent_router.py`) for: opening hours, menu with prices (Ecwid), allergens/ingredients disclaimers, blackout dates (Ecwid), and simple FAQs.
- If the question is outside scope, it falls back to the legacy KB retrieval.

## Migration Plan (Backend)

1. Ecwid calls → `ecwid_client.py` (done).
2. Constraints inference → `order_constraints.py` (done).
3. Add `routers/orders.py` with v2 endpoints (done) and progressively move v1 endpoints from `app.py` into the router.
4. Once stabilized, switch frontend to v2 endpoints and remove v1 duplicates.

## Migration Plan (Frontend)

1. Extract `frontend/order/api.js`, `state.js` (done) and progressively replace in `chat.js`.
2. Extract `calendar.js` and `ui.js`, then add `controller.js` to orchestrate.
3. Replace legacy in‑chat ordering calls with `startOrderFlow(lang)` and remove old inline code.

## Configuration

- `.env` variables:
  - `ECWID_STORE_ID`, `ECWID_API_TOKEN` – required for Ecwid calls.
  - `ECWID_MIN_LEAD_MINUTES` (default 720), `ECWID_MAX_ORDER_DAYS` (default 60) – development overrides.
  - `PRIMARY_LANG`, `LANGUAGE_POLICY`, `OPENAI_API_KEY`, etc.
