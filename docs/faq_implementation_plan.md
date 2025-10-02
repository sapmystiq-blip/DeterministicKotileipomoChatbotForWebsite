# FAQ Implementation Plan

## Phase 1 – Data Modeling & Content Prep
1. Define canonical slugs for every level in `docs/faq_inventory.md` (e.g., `tutustu`, `menu/karjalanpiirakat`). Add a conversion script that emits:
   - `docs/faq_tree.json` — nested `{ id, label_fi, label_en, children[] }` for menu rendering.
   - `docs/faq_entries.json` — flat list with `id`, `category_path`, `question_id`, `source_refs`.
2. Update `backend/knowledgebase/faq.json` to include `category_path` (array of slugs) and keep legacy `tags` for backwards compatibility. Existing `FaqItem` model in `backend/kb_models.py` needs a new `category_path: List[str]` field plus validation to ensure it matches the tree.
3. Add translation stubs for Swedish/English where missing so the UI can surface multilingual labels without breaking (fallback to Finnish if translations unavailable).
4. Version the KB export (e.g., `faq_version`: timestamp) so frontend can cache bust when hierarchy changes.

## Phase 2 – Backend APIs & Retrieval
1. Create `backend/routers/faq.py` with endpoints:
   - `GET /faq/tree` → returns the nested category structure with localized labels.
   - `GET /faq/entries?path=menu.karjalanpiirakat` → returns questions & answers under a given path.
2. Register the new router in `backend/app.py`, ensure CORS/headers match existing chat usage.
3. Extend `intent_router.py` (or wherever FAQ answers are fetched) to accept an optional `category_path` for deterministic lookup before falling back to LLM/RAG search.
4. Update any caching layers to memoize the tree + entries, invalidating when `faq_version` changes.
5. Add unit tests (pytest) covering:
   - Tree validation (all `category_path` values exist in the tree).
   - Endpoint contract (200 responses, empty states, invalid path).
   - Legacy intent flow still works with free-text questions.

## Phase 3 – Frontend UX
1. Introduce a dedicated FAQ launcher in `frontend/index.html` (e.g., a “Quick answers” button within the chat widget header) that opens the category selector.
2. In `frontend/chat.js`:
   - Fetch `/faq/tree` on load; build a client-side breadcrumbs stack.
   - Render options as buttons/cards; when a terminal node is reached call `/faq/entries` and display selectable questions.
   - On question selection, inject the answer into the chat log (distinguish between FAQ answer vs. generated responses).
   - Provide back navigation and a “Ask something else” action to return to free-text chat.
3. Update `frontend/styles.css` to support hierarchical menus (responsive columns on desktop, stacked list on mobile) and highlight active breadcrumbs.
4. Ensure assistive attributes (ARIA roles, keyboard navigation) are added for accessibility.
5. Preserve existing order flow interactions; verify the new FAQ UI does not clash with `order/` scripts or `chat.js` order states.

## Phase 4 – Content Operations & Tooling
1. Document the content-update workflow: edit `docs/faq_inventory.md` → run conversion script → commit generated JSON → deploy.
2. Provide a lint command (e.g., `python scripts/validate_faq.py`) that checks for duplicate IDs, missing translations, and orphaned paths. Hook it into CI or pre-commit if available.
3. For RAG mode (`ENABLE_RAG=1`), map category slugs to RAG document tags so category selection can seed the retriever with boosted context.

## Phase 5 – QA, Testing & Launch
1. Manual test matrix covering:
   - Finnish/English chat language toggle.
   - Selecting every top-level category and at least one leaf.
   - Switching from FAQ browsing to order placement mid-conversation.
   - Mobile view (narrow width) for breadcrumb overflow.
2. Regression tests: rerun existing automated suites (`pytest`, `npm`/`vite` if applicable) and add screenshots or short Loom for the new flow.
3. Rollout checklist:
   - Deploy backend first, confirm `/faq/tree` responds.
   - Deploy frontend; verify cache bust via `?v=<faq_version>` query appended to script tag.
   - Monitor server logs for fallback triggers (missing category) and adjust content as needed.
4. Post-launch iteration: collect real chat transcripts tagged with category path to identify missing questions or confusing labels; feed insights back into `docs/faq_inventory.md`.
