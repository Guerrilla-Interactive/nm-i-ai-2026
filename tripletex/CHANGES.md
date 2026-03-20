# Tripletex Agent — Changes & Fixes Since Initial PR

All changes made to the Tripletex AI Accounting Agent after the initial commit (`61dba95` by Pelle, Mar 20 09:55). Covers 14 subsequent commits across two branches (`main` and `kevin`) over ~7 hours on March 20, 2026.

---

## Baseline: What Pelle Shipped (`61dba95`)

- FastAPI endpoint `POST /solve` with Gemini-powered LLM classification
- 26 task types in `TaskType` enum (Tier 1–3)
- Executor with handlers for core CRUD: customer, employee, invoice, product, department, project, contact, travel expense
- `TripletexClient` with Basic Auth and single retry on 5xx
- Rule-based keyword classifier in `main.py` as fallback
- Claude classifier for local dev

---

## Timeline of Changes

### 1. Documentation (`c52e20c` — 13:57)

**Author:** Kevin Minh

Added `CLAUDE.md` at both root and `tripletex/` levels:
- Architecture overview, command reference, API gotchas, scoring details
- LLM mode selection docs (Gemini / Claude / rule-based)
- Tripletex API pitfalls discovered during testing (bank account prerequisite, version field, immutable employee email, etc.)

---

### 2. The Big Fix (`ec95c1a` — 14:04)

**Author:** frikk-gyldendal
**Files:** `classifier.py`, `executor.py`, `main.py` (+557 / −28 lines)

The single largest commit — a comprehensive bug-fix round that addressed multiple sandbox test failures.

#### Classifier fixes
- **Retry on UNKNOWN**: `MAX_RETRIES` increased from 1→3 with exponential backoff; Gemini retries if it returns `UNKNOWN` on first attempt
- **Last-resort heuristic**: Added `_last_resort_classify()` — a 26-entry single-word keyword heuristic covering all 30 task types across 7 languages, so `UNKNOWN` is near-impossible
- **JSON parse safety**: Wrapped `json.loads()` in try/except with descriptive error logging instead of silent crash
- **Keyword coverage**: Added missing keyword entries for `UPDATE_CONTACT`, `DELETE_CUSTOMER`, and other task types

#### Executor fixes
- **Product number collisions** (bug): Products with duplicate numbers caused 422 "Produktnummeret X er i bruk". Fix: search for existing product by name first, only include `number` field if explicitly provided, auto-retry without number on 422
- **VAT type fallback**: Expanded hardcoded fallback from 2 rates (0%, 25%) to 5 rates (0%, 12%, 15%, 25%, and a catch-all). Handles sandbox 404s when dynamic VAT lookup fails
- **Credit note resolution by customer name**: Added `_resolve_invoice_by_identifier()` — when invoice identifier is non-numeric, searches invoices by customer name extracted from the identifier string
- **Payment amount validation**: Before paying an invoice, fetches actual `amountOutstanding` to avoid "ugyldig beløp" (invalid amount) errors. Adjusts payment to match what's actually owed
- **Invoice line product reuse**: Before creating a new product for an invoice line, searches for existing product by name to avoid collision

#### main.py fixes
- **Credential debug logging**: Logs token length and last 4 chars on every request for 403 diagnosis
- **Keyword fallback strengthening**: Added last-resort single-word heuristic mirroring the classifier's approach

---

### 3. Gemini Model Upgrades (`5b1bced` + `1020cbc` — 14:26–14:30)

**Author:** frikk-gyldendal
**Branch:** `main` (diverged from `kevin` at this point)

Two commits on the `main` branch upgrading the Gemini model:
1. **`5b1bced`**: Switched from Vertex AI client to API-key mode (`genai.Client(api_key=...)`) — works everywhere without region issues. Model changed to `gemini-2.5-flash`
2. **`1020cbc`**: Upgraded to `gemini-2.5-pro` with 8K thinking budget (`ThinkingConfig(thinking_budget=8192)`) for better classification accuracy

---

### 4. Infrastructure + New Task Types (`339a4b2` — 16:28)

**Author:** Kevin Minh
**Files:** 9 files changed (+1,151 / −42 lines)

Massive commit covering infrastructure, new task types, efficiency caching, and field extraction improvements.

#### New task types added
- **`CREATE_SUPPLIER`** — Register suppliers (leverandør/Lieferant/fournisseur) with org number, email, phone
- **`CREATE_SUPPLIER_INVOICE`** — Incoming invoices (leverandørfaktura/Eingangsrechnung) with account mapping
- **`CREATE_DIMENSION_VOUCHER`** — Custom accounting dimensions with values, plus optional voucher posting linked to dimension values

#### Efficiency caching
- **Per-request caches** for bank account status, payment types, and VAT types — keyed by `id(client)` to avoid stale state across requests. Eliminates redundant API calls that hurt efficiency scoring
- Bank account configuration (`_ensure_bank_account`) only checks once per request instead of every invoice

#### Field extraction improvements (main.py)
- **Employee search**: Single-name fallback — when only one name is given, tries firstName then fetches all employees to search by lastName
- **Organization number cleaning**: `_clean_org_number()` strips dashes and spaces from org numbers (e.g., "922-976-457" → "922976457")
- **Dimension extraction**: Parses quoted values for dimension names and values, detects linked dimension values via multilingual keywords (verknüpft/linked/knyttet/lié/vinculado)
- **Supplier name extraction**: Regex handles common suffixes (AS, GmbH, Ltd, Inc, etc.)
- **Batch detection**: `_detect_batch()` function detects multi-entity creation patterns ("Create three departments: X, Y, Z") and returns per-entity field dicts

#### Keyword classifier enhancements
- Added patterns for supplier, supplier invoice, dimension, cost center, custom dimension
- Expanded regex to use `\w*` suffixes for department/avdeling word stems (catches declinations)
- Reordered `SET_EMPLOYEE_ROLES` before `UPDATE_EMPLOYEE` to catch "endre rolle" correctly
- Added single-name fallback for employee extraction
- Added `activar`/`ativar`/`activate` to module enable patterns
- Added voucher reversal pattern to error correction

#### Classifier prompt improvements
- Added German examples for dimension voucher creation
- Added German supplier registration example
- Added "CRITICAL: Lieferant ≠ customer" disambiguation rule
- Added "NEVER fabricate" instruction for emails, phones, addresses

#### Infrastructure
- Updated `deploy.sh` and `run_local.sh`
- Enhanced `test_harness.py` with more test cases
- Added `TripletexClient` methods: `create_travel_expense_per_diem_compensation`, `create_travel_expense_mileage_allowance`, `get_dimension_names`, `create_dimension_name`, `create_dimension_value`

---

### 5. Payroll Task Type (`788c11b` + `df6e411` — 16:30–16:34)

**Author:** Kevin Minh

Two commits adding payroll support:

1. **`788c11b`**: Added `RUN_PAYROLL` to `task_types.py`, classifier keywords, and `TripletexClient` methods (`get_salary_types`, `get_salary_payslips`, `create_salary_payslip`, `create_salary_transaction`)
2. **`df6e411`**: Full executor implementation (`_exec_run_payroll`) — finds employee, attempts salary payslip API, creates transactions for base salary + bonus. Added keyword patterns in `main.py`. Removed the earlier `CHANGELOG.md` file.

---

### 6. Payroll + Credit Note Enhancements (`d7f8c75` — 16:35)

**Author:** Kevin Minh
**Files:** `classifier.py`, `executor.py`, `main.py` (+124 / −71 lines)

#### Payroll strategy rewrite
- Replaced salary payslip API approach with voucher-based posting as primary strategy
- Voucher approach: debit 5000 (salary expense) + 5020 (bonus), credit 2780 (salary payable)
- Salary API kept as fallback but voucher is more reliable in sandbox

#### Credit note — "payment returned/bounced" recognition
- Added classifier rule: "payment returned/bounced/devolvido/rückerstattet by bank" maps to `CREATE_CREDIT_NOTE` (not `ERROR_CORRECTION`)
- Added keyword patterns in `main.py` for bounced payment detection in 6 languages
- Positioned before error correction patterns so it matches first

---

### 7. Invoice Processing + Credit Note Recognition (`90ca4c4` — 16:40)

**Author:** Kevin Minh
**Files:** `classifier.py`, `executor.py` (+159 / −20 lines)

#### Invoice with payment — existing invoice detection
- Before creating a new invoice+payment, checks if an unpaid invoice already exists for the customer
- If found, registers payment on the existing invoice instead of creating a duplicate
- Searches by customerId across all date ranges

#### Credit note — customer-based invoice lookup
- When no invoice ID is available, tries to find invoices by customer name or org number
- Falls back to creating a prerequisite chain if needed

#### Dimension voucher — improved creation flow
- Better handling of dimension rename vs. creation
- Improved error recovery when dimension already exists

#### Portuguese credit note example
- Added few-shot example for payment-returned scenario in Portuguese

---

### 8. Dimension Value Creation Refactor (`7f546dc` — 16:41)

**Author:** Kevin Minh
**Files:** `executor.py` (+33 / −19 lines)

- Used `displayName` (in addition to `name`) when matching existing dimensions — some sandbox entries use different fields
- Refactored dimension value creation loop: extracted `dim_name_ref` once instead of rebuilding `{"id": dim_id}` in every iteration
- Better error handling with search-before-create for dimension values

---

### 9. Payroll Processing Refinements (`540f448` — 16:43)

**Author:** Kevin Minh
**Files:** `executor.py` (+37 / −59 lines)

- Removed second attempt at salary payslip API — goes straight to voucher posting
- Simplified the payroll flow: find employee → create voucher with salary/bonus lines
- Uses account 5000 for salary expense, 5020 for bonus, 2780 for salary payable (credit)

---

### 10. Travel Expense + Project Updates (`5f6f3d2` — 17:05)

**Author:** Kevin Minh
**Files:** `executor.py`, `task_types.py` (+3 lines)

#### Travel expense per diem location derivation
- Location for per diem compensations now falls back through: `destination` → `departure_from` → `title` → "Norge"
- Per diem count accepts `quantity` and `days` as aliases for `count`

#### Fixed-price project support
- Added `is_fixed_price` and `fixed_price` fields to `UPDATE_PROJECT` task type spec
- Executor passes these through when updating projects

---

### 11. Supplier Invoice — Voucher Type + Error Recovery (`97df068` — 17:09)

**Author:** Kevin Minh
**Files:** `executor.py`, `task_types.py` (+57 / −9 lines)

#### Voucher type selection for supplier invoices
- Before creating a supplier invoice voucher, looks up voucher types and selects one matching "leverandør", "inngående", "supplier", "incoming", or "memorial" — avoids 422 "system-generated voucher type" rejection
- Wrapped voucher creation in try/except with descriptive error logging

#### Task type spec update
- Added `vat_percentage` to `CREATE_SUPPLIER_INVOICE` optional fields

---

### 12. Voucher Type Caching + Global Application (`8f558c9` — 17:12)

**Author:** Kevin Minh
**Files:** `executor.py` (+35 / −24 lines)

#### Centralized voucher type helper
- Extracted `_get_voucher_type_id()` — a cached, reusable function for looking up voucher types by keyword preference
- Uses per-request cache (`_cached_voucher_types` keyed by `id(client)`) to avoid repeated API calls
- Accepts `preferred_keywords` list for context-specific type selection

#### Applied voucher types across all voucher-creating handlers
- **Bank reconciliation**: uses voucher type matching "bank" / "innbetaling"
- **Error correction**: uses "korreksjon" / "correction"
- **Year-end closing**: uses "årsavslutning" / "year-end" / "closing" (replaced inline lookup)
- **Payroll**: uses "lønn" / "salary" / "payroll"
- **Supplier invoice**: uses cached helper instead of inline lookup
- **Dimension voucher**: uses default voucher type via helper

This prevents 422 errors from Tripletex rejecting vouchers with system-generated or missing voucher types.

---

## Summary by Category

### Bug Fixes
| Fix | Commit | Impact |
|-----|--------|--------|
| Product number 422 collisions | `ec95c1a` | Products with duplicate numbers failed to create |
| VAT type 404 fallback | `ec95c1a` | Invoice creation failed when dynamic VAT lookup returned nothing |
| Credit note resolution by customer | `ec95c1a` | Non-numeric invoice identifiers caused "cannot resolve" errors |
| Payment amount mismatch | `ec95c1a` | Paying wrong amount caused "ugyldig beløp" API errors |
| Invoice line product reuse | `ec95c1a` | Duplicate products created per invoice line |
| Gemini returns UNKNOWN | `ec95c1a` | No retry → task unclassified → failure |
| JSON parse crash | `ec95c1a` | Malformed LLM response crashed classifier silently |
| Org number with dashes | `339a4b2` | "922-976-457" not matching Tripletex format |
| Single-name employee search | `339a4b2` | "ansatt Nordmann" failed (only firstName searched) |
| Dimension displayName mismatch | `7f546dc` | Existing dimensions not found when API uses `displayName` |
| Payment on existing invoice | `90ca4c4` | Created duplicate invoice instead of paying existing one |
| Bounced payment misclassified | `d7f8c75` | "Payment returned by bank" routed to error correction instead of credit note |
| Missing voucher type → 422 | `97df068` | Vouchers rejected as "system-generated" without explicit type |

### New Task Types (4 added, 26→30)
| Task Type | Commit | Description |
|-----------|--------|-------------|
| `CREATE_SUPPLIER` | `339a4b2` | Register new suppliers |
| `CREATE_SUPPLIER_INVOICE` | `339a4b2` | Incoming/purchase invoices |
| `CREATE_DIMENSION_VOUCHER` | `339a4b2` | Custom accounting dimensions + voucher posting |
| `RUN_PAYROLL` | `788c11b` | Salary and bonus processing via voucher postings |

### Efficiency Optimizations
| Optimization | Commit | Savings |
|-------------|--------|---------|
| Per-request VAT type cache | `339a4b2` | 1 API call instead of N per invoice |
| Per-request payment type cache | `339a4b2` | 1 API call instead of N per payment |
| Bank account check cache | `339a4b2` | 1 check per request instead of per invoice |
| Existing product reuse | `ec95c1a` | Avoids creating duplicate products |
| Existing invoice detection | `90ca4c4` | Avoids duplicate invoice + payment chain |
| Per-request voucher type cache | `8f558c9` | 1 API call instead of N per voucher creation |

### Classifier Improvements
| Improvement | Commit |
|------------|--------|
| 3× retry with exponential backoff on UNKNOWN | `ec95c1a` |
| Last-resort 26-entry multilingual keyword heuristic | `ec95c1a` |
| Gemini 2.5-pro with 8K thinking budget | `1020cbc` |
| API-key mode (no Vertex AI region dependency) | `5b1bced` |
| Batch detection for multi-entity prompts | `339a4b2` |
| German/Portuguese few-shot examples | `339a4b2`, `90ca4c4` |
| Supplier ≠ customer disambiguation | `339a4b2` |
| Bounced payment → credit note routing | `d7f8c75` |

---

## API Gotchas Discovered During Development

These are hard-won facts from sandbox testing — each caused at least one failed submission:

1. **Product numbers collide silently**: If you POST a product with a `number` that already exists, you get 422. Must search first or omit number.
2. **VAT type lookup can 404**: The `typeOfVat=outgoing` filter sometimes returns empty. Need hardcoded fallback table.
3. **`amountOutstanding` ≠ `amount`**: Must use `amountOutstanding` when paying invoices to avoid "ugyldig beløp" (invalid amount).
4. **Employee search only supports `firstName` and `email`**: `lastName`, `name`, `departmentId` params are ignored. Must fetch all and filter client-side.
5. **Organization numbers with dashes**: Tripletex expects clean numeric format. Strip dashes/spaces before API calls.
6. **Bank account prerequisite**: Must configure ledger account 1920 with a `bankAccountNumber` before creating any invoice.
7. **Dimension `displayName` vs `name`**: Some dimension entries use `displayName` while others use `name`. Check both.
8. **Salary API limitations**: The `/salary/payslip` and `/salary/transaction` endpoints have strict requirements. Voucher-based postings (debit 5000/credit 2780) are more reliable.
9. **Invoice deduplication**: When asked to "pay invoice for customer X", must check if an unpaid invoice exists before creating a new one.
10. **"Payment returned" ≠ error correction**: Bank-bounced payments should create credit notes (reverse payment + reopen invoice), not error corrections.
11. **Voucher type is required**: Creating a voucher without an explicit `voucherType` causes 422 "system-generated voucher type" rejection. Must look up available types and pick one matching the context (supplier, bank, salary, etc.).
