# Copilot Instructions for KotileipomoChatbotForWebsite

## Project Overview
- **Purpose:** Q&A chatbot for a bakery, with in-chat ordering, built on FastAPI (backend) and vanilla JS (frontend).
- **Major Components:**
  - `frontend/`: Chat widget UI, order flow modules.
  - `backend/`: FastAPI app, API routes, Ecwid integration, knowledge base (KB) logic.
  - `backend/knowledgebase/`: JSON files for hours, FAQ, allergens, product aliases, etc.
  - `kotileipomo-rag/`: Optional hybrid RAG (retrieval-augmented generation) for advanced KB retrieval.

## Architecture & Data Flow
- **Frontend** calls backend `/api/*` endpoints for chat, product info, and order placement.
- **Backend** loads KB JSON at startup, routes chat via deterministic intent router, and integrates with Ecwid for live product/order data.
- **Order flow:** All constraints (lead time, blackout, max days) are enforced server-side, even if UI is bypassed.
- **RAG:** If enabled, uses `kotileipomo-rag` for hybrid retrieval; otherwise, falls back to deterministic KB.

## Developer Workflows
- **Setup:**
  - Python 3.10+ recommended. Install backend deps: `pip install -r backend/requirements.txt`.
  - Optional: `pip install eval_type_backport` for Python <3.10.
- **Run:**
  - `uvicorn backend.app:app --host 0.0.0.0 --port 8000`
  - Open [http://localhost:8000](http://localhost:8000)
- **Test:**
  - All: `python -m unittest discover -s tests -p "test_*.py" -v`
  - Single: `python -m unittest tests.test_constraints -v`
  - Manual API checks: see `README.md` for `curl` examples.
- **Deploy:**
  - See `nixpacks.toml` and `Procfile` for Railway/Render. Ensure Python 3.10+.

## Project-Specific Patterns & Conventions
- **KB Editing:**
  - Update JSON in `backend/knowledgebase/` and restart server. Validation is automatic.
- **API Routing:**
  - v1 endpoints in `backend/app.py`, v2 in `backend/routers/` (migrating to v2).
- **Order Constraints:**
  - All logic in `backend/order_constraints.py`. Test with `tests/test_constraints.py`.
- **Frontend Order Flow:**
  - Modularized in `frontend/order/` (see `controller.js`, `api.js`, `state.js`).
- **Environment Variables:**
  - `PRIMARY_LANG`, `LANGUAGE_POLICY`, `OPENAI_API_KEY`, `LLM_ENABLED`, `ECWID_STORE_URL`, etc. (see `README.md`).
- **RAG Integration:**
  - Build index: `python kotileipomo-rag/scripts/build_index.py`
  - Query: `python kotileipomo-rag/scripts/query.py "question" --lang fi`

## Key Files & References
- `docs/ARCHITECTURE.md`: High-level architecture, migration plans, and KB structure.
- `README.md`: Setup, environment, testing, and deployment details.
- `backend/intent_router.py`: Core chat/intent logic.
- `backend/order_constraints.py`: Order validation logic.
- `kotileipomo-rag/README.md`: RAG usage and structure.

## Tips for AI Agents
- Always validate KB JSON after edits; fallback logic is robust but errors are logged.
- When adding endpoints, prefer v2 routers and update both backend and frontend as needed.
- For new order logic, ensure server-side validation covers all constraints (lead, blackout, max days).
- Use provided test modules as templates for new tests.
