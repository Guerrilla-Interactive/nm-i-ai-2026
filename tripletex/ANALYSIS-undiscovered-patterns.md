# Undiscovered Task Patterns — Gap Analysis

**Generated:** 2026-03-21
**Scope:** Patterns users/grader could ask that our 30+ task types DON'T currently handle

---

## 1. Multi-Entity Batch Operations

**Currently handled:** Only partially. `CREATE_DEPARTMENT` has been seen with batch ("Create three departments: X, Y, Z") but the executor creates one at a time via the classifier loop.

**Gaps:**
- "Opprett 5 ansatte med følgende detaljer: ..." — batch employee creation
- "Lag 3 fakturaer til forskjellige kunder" — batch invoice creation
- "Opprett produktene A, B og C med priser 100, 200, 300 kr" — batch product creation
- "Slett alle prosjekter som starter med Test" — conditional batch delete

**Risk:** MEDIUM. The grader has confirmed batch department creation (prompt #6: "Create three departments in Tripletex: Utvikling, Innkjop, and Salg"). The classifier needs to detect batch intent and loop. If the classifier returns a single TaskType but the prompt contains multiple entities, only the first gets created.

**Recommendation:** Add batch detection in classifier — split into N classifications when "X, Y, and Z" pattern is detected.

---

## 2. Chained/Multi-Step Workflows (Beyond What We Have)

**Currently handled:** INVOICE_WITH_PAYMENT (create customer + invoice + payment), PROJECT_WITH_CUSTOMER (create project linked to customer), CREATE_EMPLOYEE + SET_EMPLOYEE_ROLES (inline role).

**Gaps:**
- "Opprett kunde Fjord AS, lag et prosjekt for dem, og fakturer 10 timer" — 3-step: customer → project → invoice
- "Opprett leverandør, registrer faktura fra dem, og betal den" — supplier → supplier invoice → payment
- "Opprett avdeling Salg, legg til ansatt Per Hansen i avdelingen" — department + assign employee
- "Lag produkt Tjeneste A, opprett faktura med dette produktet til kunde X" — product → invoice
- "Opprett prosjekt, legg til deltaker, loggfør timer" — project → participant → timesheet

**Risk:** MEDIUM-HIGH. The grader has already shown multi-step patterns (confirmed prompts #2 and #7). Tier 3 likely has more complex chains.

**Recommendation:** Consider a META_CHAIN task type that decomposes into sequential executor calls, or enhance the UNKNOWN handler to chain multiple task types.

---

## 3. Vague/Conversational Prompts

**Currently handled:** Classifier uses LLM, so it can handle some vagueness. UNKNOWN fallback exists.

**Gaps:**
- "Jeg trenger å fikse lønna til Lars" — unclear: update salary? run payroll? correct a salary transaction?
- "Noe er galt med fakturaen" — no invoice number, no specifics
- "Kan du hjelpe meg med regnskapet?" — too vague to classify
- "Sjekk om alt er i orden med kunde Fjord AS" — query, not action
- "Hva skjedde med bilag 1234?" — informational query, not correction
- "Vi må gjøre noe med MVA-oppsettet" — VAT configuration change

**Risk:** LOW-MEDIUM. Grader prompts so far have been specific and action-oriented. Unlikely to send truly vague prompts, but Tier 3 may include ambiguous scenarios.

**Recommendation:** Improve UNKNOWN executor to attempt best-effort interpretation using the LLM, and return informative error messages.

---

## 4. Reference to Previous Entities (Sequential Context)

**Currently handled:** NOT AT ALL. Each request is stateless.

**Gaps:**
- "Lag en faktura til kunden vi nettopp opprettet" — references entity from prior request
- "Legg til en kontaktperson for den samme kunden" — "den samme" = the same
- "Registrer betaling for den fakturaen" — "den" = that one
- "Oppdater prosjektet vi snakket om" — conversational reference

**Risk:** HIGH. If the grader sends sequential tests where test N references the result of test N-1, we will fail completely. The prompt says "sequential grader tests" are possible.

**Recommendation:** This is a fundamental architecture gap. Options:
1. Store last-created entity IDs in a session/state store keyed by entity type
2. Search for recently-created entities when references like "nettopp opprettet" / "just created" are detected
3. Add a "last entity" field to the classifier output

---

## 5. Correction/Undo Operations

**Currently handled:** ERROR_CORRECTION (reverse/delete voucher), REVERSE_PAYMENT, CREATE_CREDIT_NOTE, DELETE_* operations.

**Gaps:**
- "Det var feil, endre tilbake" — generic undo with no specifics
- "Angre siste" — undo last action (requires state tracking)
- "Rett opp kundenavnet, det skal være Fjord AS ikke Ford AS" — correction that's really an UPDATE
- "Slett den siste fakturaen jeg opprettet" — delete with implicit reference
- "Korriger beløpet på faktura 10042 fra 5000 til 7000" — partial correction (update invoice amount)

**Risk:** MEDIUM. Generic undo requires state tracking (gap #4). Specific corrections map to existing UPDATE/DELETE types if classifier extracts correctly.

**Recommendation:** Map "rett opp" / "korriger" + entity type → corresponding UPDATE_* task type. "Angre siste" requires session state.

---

## 6. Report/Query Operations

**Currently handled:** FIND_CUSTOMER, FIND_SUPPLIER (search only).

**Gaps — entirely missing task types:**

| Pattern | Example Prompt | API Endpoint |
|---------|---------------|--------------|
| LIST_INVOICES | "Vis meg alle fakturaer fra mars" | GET /invoice |
| INVOICE_STATUS | "Hva skylder Acme oss?" / "Outstanding invoices for customer X" | GET /invoice?invoiceStatus=InvoiceStatusUnpaid |
| ACCOUNT_BALANCE | "Hva er saldoen på konto 1920?" | GET /ledger/account/{id} |
| BALANCE_SHEET | "Vis balansen per 31.03.2026" | GET /ledger/annualAccount |
| PROFIT_LOSS | "Vis resultatregnskapet for Q1 2026" | GET /resultBudget or /ledger/annualAccount |
| LIST_EMPLOYEES | "Vis alle ansatte" / "Hvem jobber i avdeling Salg?" | GET /employee |
| LIST_PRODUCTS | "Vis alle produkter med pris over 1000 kr" | GET /product |
| LIST_SUPPLIERS | "Vis alle leverandører" | GET /supplier |
| PROJECT_STATUS | "Hva er status på prosjekt Alpha?" | GET /project/{id}/period/overallStatus |
| PAYSLIP_QUERY | "Vis lønnsslipp for Per Hansen mars 2026" | GET /salary/payslip |
| VOUCHER_DETAILS | "Vis bilag 1234" | GET /ledger/voucher/{id} |
| TIMESHEET_SUMMARY | "Hvor mange timer har Per logget denne uken?" | GET /timesheet/entry |

**Risk:** HIGH. Query/report tasks are natural for an "AI accounting agent." The grader may well ask "show me all invoices" or "what's the balance." We return error or misclassify as UNKNOWN.

**Recommendation:** Add at minimum: LIST_INVOICES, INVOICE_STATUS, LIST_EMPLOYEES, VOUCHER_DETAILS. These are simple GET operations.

---

## 7. Search Operations (Beyond FIND_CUSTOMER/FIND_SUPPLIER)

**Currently handled:** FIND_CUSTOMER (search by name/org), FIND_SUPPLIER (search by name/org).

**Gaps:**
- "Finn alle leverandører i Oslo" — search by address (not supported in FIND_SUPPLIER)
- "Hvem er ansatt på avdeling 42?" — FIND_EMPLOYEE (doesn't exist)
- "Finn alle fakturaer over 10000 kr" — FIND_INVOICE (doesn't exist)
- "Finn alle prosjekter for kunde Fjord AS" — FIND_PROJECT (doesn't exist)
- "Søk etter produkter med 'konsulent' i navnet" — FIND_PRODUCT (doesn't exist)
- "Finn kontaktperson for kunde X" — FIND_CONTACT (doesn't exist)

**Risk:** MEDIUM. The grader confirmed FIND_CUSTOMER exists. FIND_SUPPLIER also exists. But other entity searches are missing.

**Recommendation:** Add FIND_EMPLOYEE, FIND_INVOICE at minimum. These are 1-API-call GET operations.

---

## 8. API Endpoints Suggesting Missing Task Types

### High-Value Missing Types (API exists, no task type)

| Missing Task Type | API Endpoints | Use Case |
|-------------------|---------------|----------|
| **CREATE_ORDER** | POST /order | "Opprett ordre til kunde X for 5 stk Produkt A" |
| **UPDATE_ORDER** | PUT /order/{id} | "Oppdater ordre 1234 med ny leveringsdato" |
| **ORDER_TO_INVOICE** | PUT /order/{id}/:invoice | "Fakturer ordre 1234" — convert order to invoice |
| **IMPORT_BANK_STATEMENT** | POST /bank/statement/import | "Importer kontoutskrift" — often paired with reconciliation |
| **CREATE_PURCHASE_ORDER** | POST /purchaseOrder | "Opprett innkjøpsordre til leverandør X" |
| **APPROVE_TIMESHEET** | PUT /timesheet/entry/:approve | "Godkjenn timer for ansatt X" |
| **PAY_SUPPLIER_INVOICE** | POST /incomingInvoice/{id}/addPayment | "Betal leverandørfaktura 1234" |
| **CREATE_ACCOUNT** | POST /ledger/account | "Opprett konto 6300 Kontorrekvisita" |
| **UPDATE_SALARY_SETTINGS** | PUT /salary/settings | "Oppdater lønnsinnstillinger" |
| **ADD_PROJECT_PARTICIPANT** | POST /project/participant | "Legg til Per Hansen som deltaker i prosjekt Alpha" |

### Medium-Value Missing Types

| Missing Task Type | API Endpoints | Use Case |
|-------------------|---------------|----------|
| SEND_INVOICE | (via order send endpoints) | "Send faktura 1234 til kunden" |
| CLOSE_PROJECT | PUT /project/{id} (isClosed=true) | "Lukk prosjekt Alpha" |
| UPLOAD_DOCUMENT | POST /documentArchive/* | "Last opp dokument til kunde X" |
| GET_EXCHANGE_RATE | GET /currency/{id}/rate | "Hva er valutakursen for EUR?" |
| CREATE_REMINDER | (reminder endpoints if available) | "Send purring for faktura 1234" |
| DELIVERY_ADDRESS | (deliveryAddress on customer/order) | "Oppdater leveringsadresse for kunde X" |

---

## 9. Specific Endpoint Groups We're Missing

### /bank/statement — Bank Statement Operations
- **Import:** POST /bank/statement/import — "Importer kontoutskrift fra fil"
- **View:** GET /bank/statement — "Vis kontoutskrift for mars"
- **Transactions:** GET /bank/statement/transaction — "Vis transaksjoner på konto 1920"
- Currently our BANK_RECONCILIATION task type exists but doesn't use statement import.

### /ledger/annualAccount — Balance Sheet & Annual Reports
- GET /ledger/annualAccount — "Vis årsregnskap 2025"
- GET /ledger/accountingPeriod — "Vis regnskapsperioder"
- No task type covers reporting/viewing financial statements.

### /order — Order Management (entirely missing)
- This is a major gap. Orders are a core accounting workflow:
  - Create order → Add lines → Send to customer → Convert to invoice
  - "Opprett ordre", "Legg til ordrelinje", "Fakturer ordren"
  - 18+ endpoints, none covered.

### /purchaseOrder — Purchase Orders (entirely missing)
- Procurement workflow: Create PO → Send to supplier → Receive goods → Confirm
- "Opprett innkjøpsordre til leverandør X for 100 stk vare Y"
- 15+ endpoints, none covered.

### /incomingInvoice — Incoming Invoice Management
- We have CREATE_SUPPLIER_INVOICE and REGISTER_SUPPLIER_INVOICE
- But missing: addPayment (POST /incomingInvoice/{id}/addPayment) — "Betal leverandørfaktura"
- Missing: update incoming invoice

### /salary/payslip — Payslip Queries
- GET /salary/payslip — "Vis lønnsslipp for Per Hansen"
- GET /salary/payslip/{id}/pdf — "Last ned lønnsslipp"
- No task type for viewing/downloading payslips.

### /documentArchive — Document Management
- Upload/download documents attached to customers, suppliers, projects, etc.
- "Last opp kontrakt til prosjekt Alpha"
- No task type for document management.

### /event/subscription — Webhooks
- Not relevant for grader tasks, but exists in the API.

---

## 10. Priority Ranking for Implementation

### P0 — Likely to appear in Tier 3 grader tests
1. **Query/report operations** — "Vis alle fakturaer", "Hva skylder kunde X?"
2. **Batch operations improvement** — Classifier must split "Create X, Y, and Z" into N tasks
3. **Sequential context** — Entity references across requests ("den kunden vi nettopp opprettet")

### P1 — Good coverage expansion, moderate effort
4. **CREATE_ORDER / ORDER_TO_INVOICE** — Core accounting workflow
5. **PAY_SUPPLIER_INVOICE** — Natural complement to CREATE_SUPPLIER_INVOICE
6. **FIND_EMPLOYEE** — Simple GET, consistent with FIND_CUSTOMER pattern
7. **ADD_PROJECT_PARTICIPANT** — Simple POST, extends project workflows
8. **CLOSE_PROJECT** — Simple PUT, extends project lifecycle

### P2 — Nice to have, lower grader probability
9. **IMPORT_BANK_STATEMENT** — Complements BANK_RECONCILIATION
10. **CREATE_PURCHASE_ORDER** — Procurement workflow
11. **APPROVE_TIMESHEET** — Extends LOG_HOURS workflow
12. **SEND_INVOICE** — Post-creation action
13. **GET_EXCHANGE_RATE** — Simple query

### P3 — Unlikely in grader, future-proofing
14. Document management operations
15. Salary/payslip queries
16. Webhook subscription management
17. Company settings modifications

---

## 11. Language Pattern Gaps

All 30+ task types have been pattern-mapped for 7 languages (nb, nn, en, de, fr, es, pt). But some verb patterns may be missing:

| Pattern | Language | Example | Risk |
|---------|----------|---------|------|
| "Vis" / "Show" | nb/en | "Vis alle kunder" | No query task types |
| "Hent" / "Fetch" | nb | "Hent faktura 1234" | Could be query or action |
| "Bestill" / "Order" | nb | "Bestill 100 stk vare X" | No ORDER task type |
| "Betal" / "Pay" | nb | "Betal leverandørfaktura" | No PAY task type |
| "Godkjenn" / "Approve" | nb | "Godkjenn timer" | No APPROVE task type |
| "Send" | nb/en | "Send faktura til kunden" | No SEND task type |
| "Lukk" / "Close" | nb | "Lukk prosjekt Alpha" | Maps to UPDATE_PROJECT but classifier may miss |
| "Avslutt" / "Finish" | nb | "Avslutt prosjektet" | Same as "Lukk" |

---

## Summary

**Total identified gaps:** ~25 missing task types + 4 architectural gaps

**Biggest risks for Tier 3 scoring:**
1. Report/query operations (12+ missing types, natural for AI agent)
2. Sequential context / entity references (architectural gap)
3. Batch operations (partially handled but fragile)
4. Order management (18+ API endpoints, 0 coverage)
5. Payment of supplier invoices (endpoint exists, no task type)
