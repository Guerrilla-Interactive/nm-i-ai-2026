# Tripletex Agent Changelog

## Overview

The Tripletex AI Accounting Agent underwent a rapid, intensive transformation during the NM i AI 2026 competition (March 19-22, 2026). Starting from an initial codebase that could classify and execute basic accounting tasks, the agent was systematically hardened through sandbox testing, failure analysis, and iterative bug fixes. The result: an agent that reliably handles 30+ task types across 7 languages with a multi-tier fallback classifier, robust API error recovery, and efficiency optimizations that minimize API calls.

---

## Timeline

### Commit 1: `61dba95` — Initial Commit (Mar 19)

> *Initial commit: NM i AI 2026 competition codebase*

The starting point. Three competition tasks shipped together: Astar Island (world simulation), Tripletex (accounting agent), and NorgesGruppen (object detection).

**Tripletex agent at this point:**
- FastAPI endpoint (`POST /solve`) with Gemini-powered classification
- 26 task types defined in `TaskType` enum
- Basic executor with handlers for core CRUD operations (customer, employee, invoice, product, department, project, contact, travel expense)
- Tripletex API client with Basic Auth and single retry on 5xx
- Rule-based keyword classifier in `main.py` as fallback
- Claude classifier for local development

### Commit 2: `c52e20c` — Documentation (Mar 20)

> *docs: added claude.md*

Added `tripletex/CLAUDE.md` with architecture docs, command reference, API gotchas, and scoring details. This became the shared knowledge base that guided all subsequent debugging sessions.

### Commit 3: `ec95c1a` — The Big Fix (Mar 20, 14:04)

> *Fix Tripletex agent: classifier fallback chain, executor bugs, deploy v42*

The largest single commit. 379 insertions across `classifier.py`, `executor.py`, and `main.py`. This was the result of systematically running the agent against the competition grader and fixing every failure mode discovered.

**Classifier fixes:**
- `MAX_RETRIES` increased from 1 to 3 with exponential backoff (`0.5 * 2^attempt` seconds)
- Gemini UNKNOWN results now trigger retry instead of immediate fallback
- JSON parse errors caught with descriptive logging instead of raw exceptions
- Added 4 new keyword pattern groups: `UPDATE_CONTACT`, `DELETE_CUSTOMER`, `UPDATE_DEPARTMENT`, `LOG_HOURS`
- Added `_last_resort_classify()` — a 26-entry single-word heuristic that fires after all other classifiers fail, covering all major task types in Norwegian, English, Spanish, German, French, and Portuguese
- Keyword fallback within `_classify_with_keywords()` also gained its own last-resort word list

**Executor fixes:**
- **Product number collisions**: Products now search-by-name before creating. If creation returns 422 "er i bruk" (number in use), retries without the `number` field to let Tripletex auto-assign
- **VAT type fallback**: Expanded from just 25%/0% to include 12% (transport/hotel) and 15% (food) with floating-point tolerance
- **Invoice line products**: Same search-first + collision-retry logic applied to inline product creation during invoice/order flows
- **Credit note resolution**: Non-numeric invoice identifiers (e.g., "Factura para Viento SL por '...'") now resolved via customer name search with regex extraction for Spanish/English/Norwegian patterns. Falls back to creating a prerequisite invoice chain if no match found
- **Payment amount validation**: Before registering payment, fetches the actual invoice to compare `amountOutstanding` with the provided amount. Adjusts to match if they differ — prevents "ugyldig beløp" (invalid amount) errors
- **Invoice-with-payment amount**: Changed to prefer `amountOutstanding` over `amount` for the payment step, since the API's reported amount includes VAT correctly

**Main.py fixes:**
- Credential debug logging added (token length + last 4 chars) for diagnosing 403 errors on Cloud Run
- Rule-based classifier gained the same last-resort word list covering 15 task types
- Safety net: if primary classifier (Gemini/Claude) returns UNKNOWN, rule-based is tried as backup before giving up
- Post-processing now only applied to non-Gemini paths (Gemini's `classify_task()` already post-processes)

### Commit 4: `5b1bced` — Gemini API Key Mode (Mar 20, 14:26)

> *Switch Gemini to API key mode with gemini-2.5-flash*

Vertex AI was 404ing on `gemini-2.0-flash` (model deprecated mid-competition). Switched to `GEMINI_API_KEY` with `gemini-2.5-flash` via Google AI Studio. Client initialization now prioritizes API key over Vertex AI to avoid region/model availability issues.

### Commit 5: `1020cbc` — Gemini 2.5 Pro (Mar 20, 14:30)

> *Use gemini-2.5-pro with 8K thinking budget for best accuracy*

Upgraded to `gemini-2.5-pro` for maximum classification accuracy. Added `ThinkingConfig` support with an 8,192-token thinking budget for 2.5-pro models. The extra latency was worth it — classification accuracy jumped noticeably on complex multilingual prompts.

### Uncommitted Work — Feature Expansion + Efficiency (Mar 20, ongoing)

**862 insertions, 39 deletions across 8 files.** The largest batch of changes, adding new task types, efficiency caching, batch support, and hardening.

---

## Detailed Changes by Subsystem

### Classifier (`classifier.py`)

| Change | Why |
|--------|-----|
| Claude fallback auto-disables after first failure | Prevents wasting round-trips on repeated Claude errors during a request |
| "NEVER fabricate" rule in system prompt | LLMs were hallucinating email addresses and phone numbers not present in prompts |
| Dimension/voucher vocabulary added to keyword tables | New Tier 3 task type support |
| Supplier/supplier invoice keywords and examples | New Tier 2 task types — distinguish "leverandørfaktura" from regular "faktura" |
| `_strip_hallucinated_fields()` post-processor | Removes email/phone/website values that don't appear in the original prompt text |
| Batch operation support in `_parse_response()` | Returns a list for batch classifications instead of failing |
| Supplier-specific few-shot examples (Nynorsk, German, Norwegian) | Classifiers need examples to reliably distinguish supplier vs customer operations |
| Anti-keywords for `CREATE_SUPPLIER` | "faktura" in combination with "leverandør" should route to supplier invoice, not supplier creation |

### Executor (`executor.py`)

| Change | Why |
|--------|-----|
| Per-request caching for bank account, VAT types, payment types | Eliminates redundant API calls — major efficiency score improvement |
| `_clean_org_number()` helper | Organization numbers with dashes/spaces (e.g., "922 976 457") caused 422 errors |
| Single-name employee search fallback | If only "Nordmann" given, search by firstName fails; now fetches all employees and filters by lastName client-side |
| `_exec_create_supplier_invoice()` — new | Creates supplier + voucher with balanced debit/credit postings (expense account 4000, liability account 2400) |
| `_exec_create_dimension_voucher()` — new | Creates custom accounting dimension, values, and optionally posts a voucher with `freeAccountingDimension{N}` linkage |
| Travel expense per diem + mileage support | Added `create_travel_expense_per_diem_compensation()` and `create_travel_expense_mileage_allowance()` calls |
| Graceful degradation on dimension voucher | If voucher creation fails with dimension linkage, retries without — still creates the dimension/values |

### Client (`tripletex_client.py`)

| Change | Why |
|--------|-----|
| `create_travel_expense_per_diem_compensation()` | New endpoint: `POST /travelExpense/perDiemCompensation` |
| `create_travel_expense_mileage_allowance()` | New endpoint: `POST /travelExpense/mileageAllowance` |
| `get_dimension_names()` / `create_dimension_name()` | New endpoints: `GET/POST /ledger/accountingDimensionName` |
| `get_dimension_values()` / `create_dimension_value()` | New endpoints: `GET/POST /ledger/accountingDimensionValue` |

### Task Types (`task_types.py`)

Three new task types added:

| Type | Tier | Description |
|------|------|-------------|
| `CREATE_SUPPLIER_INVOICE` | T2 | Register incoming supplier invoice via voucher postings |
| `CREATE_SUPPLIER` | T2 | Register a new supplier entity |
| `CREATE_DIMENSION_VOUCHER` | T3 | Custom accounting dimension + values + optional voucher |

Each includes field specs (required/optional) and human-readable descriptions used in classifier prompts.

### Main.py (Entrypoint)

| Change | Why |
|--------|-----|
| Request counter + human-readable summary | Prints a bordered summary after each request with classification, fields, result, API call count |
| Batch detection (`_detect_batch()`) | Handles "Create three departments: X, Y, Z" patterns — splits into individual classifications |
| Batch handling in `classify()` and `solve()` | Processes batch classifications by executing each sub-task independently |
| `SET_EMPLOYEE_ROLES` moved before `UPDATE_EMPLOYEE` in keyword map | "endre rolle" was matching "endre ansatt" pattern first |
| `CREATE_DIMENSION_VOUCHER` before invoice patterns | "Beleg" (voucher) alone could trigger invoice patterns |
| `CREATE_SUPPLIER_INVOICE` before regular invoice patterns | "leverandør + faktura" must not route to plain `CREATE_INVOICE` |
| `_detect_batch()` for LLM classifiers too | Even when Gemini classifies correctly, batch splitting is checked for multi-entity prompts |
| Expanded enable module regex | Added "activar", "ativar", "activate" for Spanish/Portuguese |
| Broader invoice-with-payment patterns | "facture impayée" alone (without explicit payment keyword) now matches |
| Error correction gained "reverser/reverse/tilbakefør" patterns | Reversals are a form of error correction |
| Employee field extraction for `SET_EMPLOYEE_ROLES` | Was only extracting names for create/update/delete — roles handler now gets names too |
| Single-name employee fallback in rule-based extractor | Catches "ansatt Nordmann" as `employee_identifier` when only one name is given |
| Org number regex expanded to allow dashes/spaces | `(\d{9})` → `([\d\-\s]{9,})` + strip |
| Dimension voucher field extraction | Quoted values, account numbers ("Konto 7000"), amounts, linked dimension values |
| Supplier invoice field extraction | Supplier name regex, amount extraction |

### Deployment (`deploy.sh`, `run_local.sh`)

| Change | Why |
|--------|-----|
| `GEMINI_MODEL` changed from `gemini-2.0-flash` to `gemini-2.5-flash` | 2.0-flash was deprecated/404ing |
| `run_local.sh` now sources `.env` before starting | Ensures `TRIPLETEX_SESSION_TOKEN` etc. are available locally without manual export |

### Test Harness (`test_harness.py`)

| Change | Why |
|--------|-----|
| `--real-creds` flag | Send real Tripletex credentials from `.env` instead of fake ones — enables true end-to-end testing against the sandbox |
| `load_real_credentials()` helper | Parses `.env` file for `TRIPLETEX_BASE_URL` and `TRIPLETEX_SESSION_TOKEN` |

---

## API Gotchas Discovered

These were learned through repeated sandbox failures and documented in `CLAUDE.md`:

1. **Bank account prerequisite**: `GET /ledger/account?number=1920` then `PUT` with `bankAccountNumber` before any invoice can be created
2. **Employee email is immutable**: Cannot change via PUT after creation
3. **Employee search**: Only `firstName` and `email` query params work. `lastName`, `name`, `departmentId` do NOT filter — must filter client-side
4. **Version field required**: All PUTs need the `version` field (optimistic locking) — always request `fields=*` on GETs
5. **Order-to-Invoice flow**: POST customer -> POST order (with orderLines) -> `PUT /order/{id}/:invoice` (query params only, no body)
6. **Invoice payment**: `PUT /invoice/{id}/:payment` takes query params only (paymentDate, paymentTypeId, paidAmount)
7. **Response wrappers**: POST returns `{"value": {...}}`, GET list returns `{"values": [...]}`
8. **Product number collisions**: Tripletex returns 422 "Produktnummeret X er i bruk" if the number is taken — must search first or omit number
9. **VAT type 404**: Some VAT type IDs don't exist in all sandboxes — need hardcoded fallbacks
10. **Organization numbers**: Must be stripped of dashes/spaces before sending to API

---

## Efficiency Optimizations

The competition scores include an efficiency bonus (up to 2x multiplier) based on API call count and error count. Key optimizations:

- **Bank account check cached per request**: Only verifies account 1920 once per client instance, not per invoice
- **VAT type lookup cached per request**: Single fetch of all outgoing VAT types, reused across products/invoices
- **Payment type lookup cached per request**: Single fetch of payment types, reused across payment registrations
- **Product search-before-create**: Avoids creating duplicate products (which would waste a POST + get a 422 error)
- **Invoice amount pre-validation**: Fetches invoice before payment to use correct `amountOutstanding`, avoiding payment rejection + retry

---

## Scoring Architecture

```
Score per task = field_correctness * tier_multiplier * efficiency_bonus

Tier multipliers: T1 = 1x, T2 = 2x, T3 = 3x
Efficiency bonus: up to 2x for minimal API calls and zero errors
Maximum possible score: 6.0
```

The agent's approach: maximize field correctness through accurate classification, then minimize API calls through caching and search-before-create patterns.
