# Analysis: Graded Logs by User Group

**Generated:** 2026-03-21
**Source:** GRADER-LOG.md (17 entries), GRADER-ANALYSIS.md (2 deep-dive), GRADER-PATTERNS.md (9 confirmed grader prompts, 30 task types projected)
**Scope:** All confirmed grader prompts + projected task-type coverage mapped to user personas

---

## 1. User Group Definitions

| User Group | Norwegian Title | Core Concerns | Task Types |
|-----------|----------------|---------------|------------|
| **SMB Owner** | Daglig leder | Invoices, customers, products, payments, basic ops | CREATE_INVOICE, CREATE_CUSTOMER, CREATE_PRODUCT, INVOICE_WITH_PAYMENT, INVOICE_EXISTING_CUSTOMER, REGISTER_PAYMENT, CREATE_CREDIT_NOTE, FIND_CUSTOMER, UPDATE_CUSTOMER, DELETE_CUSTOMER |
| **HR Manager** | Personalansvarlig | Employees, salaries, departments, travel expenses | CREATE_EMPLOYEE, UPDATE_EMPLOYEE, DELETE_EMPLOYEE, SET_EMPLOYEE_ROLES, CREATE_TRAVEL_EXPENSE, DELETE_TRAVEL_EXPENSE, RUN_PAYROLL, CREATE_DEPARTMENT, UPDATE_DEPARTMENT, DELETE_DEPARTMENT |
| **Project Manager** | Prosjektleder | Projects, time tracking, billing, contacts | CREATE_PROJECT, PROJECT_WITH_CUSTOMER, PROJECT_BILLING, UPDATE_PROJECT, DELETE_PROJECT, LOG_HOURS, CREATE_CONTACT, UPDATE_CONTACT |
| **Accountant** | Regnskapsfører | Vouchers, postings, VAT, year-end, reconciliation | BANK_RECONCILIATION, ERROR_CORRECTION, YEAR_END_CLOSING, CREATE_DIMENSION_VOUCHER, REVERSE_PAYMENT |
| **Supplier Manager** | Innkjøpsansvarlig | Suppliers, purchase orders, vendor invoices | CREATE_SUPPLIER, UPDATE_SUPPLIER, DELETE_SUPPLIER, FIND_SUPPLIER, CREATE_SUPPLIER_INVOICE, REGISTER_SUPPLIER_INVOICE |
| **System Admin** | Systemansvarlig | Modules, company settings, config | ENABLE_MODULE |

---

## 2. Prompt-by-Prompt User Group Mapping

### Confirmed Grader Prompts (from production logs)

| # | Lang | Prompt (truncated) | Task Type | User Group | Mental Model | Outcome |
|---|------|-------------------|-----------|-----------|--------------|---------|
| 1 | nb | "Lag faktura til kunde Nordfjord AS: 2 stk Konsulenttjeneste til 1500 kr" | CREATE_INVOICE | **SMB Owner** | Expects customer to be created if new; expects invoice lines with correct quantities & prices | SUCCESS |
| 2 | nn | "Opprett prosjektet 'Analyse Sjøbris' knytt til kunden Sjøbris AS (org.nr 883693329). Prosjektleiar er Steinar Berge..." | PROJECT_WITH_CUSTOMER | **Project Manager** | Expects customer creation + project linkage + PM assignment in one atomic operation | SUCCESS |
| 3 | nn | "Opprett ein ny avdeling som heiter Marknadsføring" | CREATE_DEPARTMENT | **HR Manager** | Expects department created with exact name as specified | FAILED (DNS) |
| 4 | nb | "Opprett prosjektet 'Test' knytt til kunden TestCorp AS..." | PROJECT_WITH_CUSTOMER | **Project Manager** | Same as #2 | FAILED (401) |
| 5 | de | "Erstellen Sie das Produkt 'Datenberatung' mit der Produktnummer 5524. Der Preis beträgt 22550 NOK ohne MwSt., mit dem Steuersatz 25%" | CREATE_PRODUCT | **SMB Owner** | Expects product with correct number, price, and VAT rate (not default 0%) | SUCCESS (partial: VAT check failed initially) |
| 7 | de | "Erstellen Sie den Kunden Grünfeld GmbH mit der Organisationsnummer 835026434. Die Adresse ist Fjordveien 105, 3015 Drammen" | CREATE_CUSTOMER | **SMB Owner** | Expects customer with org nr + full address parsed correctly | SUCCESS |
| 8 | en | "Create three departments in Tripletex: 'Utvikling', 'Innkjøp', and 'Salg'." | CREATE_DEPARTMENT (batch) | **HR Manager** | Expects batch creation of 3 departments in one prompt | FAILED (batch → UNKNOWN) |
| 9 | nb | "Vi har en ny ansatt som heter Astrid Strand, født 4. May 1986. Opprett vedkommende som ansatt med e-post astrid.strand@e..." | CREATE_EMPLOYEE | **HR Manager** | Expects employee with birth date parsed (mixed-lang format) + email; expects startDate defaulted | FAILED (422: missing startDate) |
| 16 | fr | "Le client Colline SARL (nº org. 850491941) a une facture impayée de 10550 NOK hors TVA pour 'Heures de conseil'. Enregistrer le paiement." | INVOICE_WITH_PAYMENT | **SMB Owner** | Expects create customer + create invoice + register payment in one compound flow. Narrative style, no invoice number = new. | FAILED (misclassified as REGISTER_PAYMENT) |
| — | nb | "Kunden Brattli AS (org.nr 909268265) har en utestående faktura på 31300 kr eksklusiv MVA for 'Konsulenttimer'. Registrer..." | INVOICE_WITH_PAYMENT | **SMB Owner** | Same compound flow pattern in Norwegian | (projected) |

### Projected Task Types by User Group (not yet seen from grader)

| User Group | Task Types Expected | # Types | Tier Coverage |
|-----------|-------------------|---------|---------------|
| SMB Owner | CREATE_INVOICE ✓, CREATE_CUSTOMER ✓, CREATE_PRODUCT ✓, INVOICE_WITH_PAYMENT ✓, INVOICE_EXISTING_CUSTOMER, REGISTER_PAYMENT, CREATE_CREDIT_NOTE, FIND_CUSTOMER, UPDATE_CUSTOMER, DELETE_CUSTOMER | 10 | T1: 5, T2: 5 |
| HR Manager | CREATE_EMPLOYEE ✓, UPDATE_EMPLOYEE, DELETE_EMPLOYEE, SET_EMPLOYEE_ROLES, CREATE_DEPARTMENT ✓, UPDATE_DEPARTMENT, DELETE_DEPARTMENT, CREATE_TRAVEL_EXPENSE, DELETE_TRAVEL_EXPENSE, RUN_PAYROLL | 10 | T1: 5, T2: 5 |
| Project Manager | CREATE_PROJECT, PROJECT_WITH_CUSTOMER ✓, PROJECT_BILLING, UPDATE_PROJECT, DELETE_PROJECT, LOG_HOURS, CREATE_CONTACT, UPDATE_CONTACT | 8 | T1: 1, T2: 7 |
| Accountant | BANK_RECONCILIATION, ERROR_CORRECTION, YEAR_END_CLOSING, CREATE_DIMENSION_VOUCHER, REVERSE_PAYMENT | 5 | T2: 1, T3: 4 |
| Supplier Manager | CREATE_SUPPLIER, UPDATE_SUPPLIER, DELETE_SUPPLIER, FIND_SUPPLIER, CREATE_SUPPLIER_INVOICE, REGISTER_SUPPLIER_INVOICE | 6 | T2: 5, T3: 1 |
| System Admin | ENABLE_MODULE | 1 | T3: 1 |

---

## 3. Cross-Tabulation: User Group × Success Rate

### By User Group (confirmed grader prompts only, n=9)

| User Group | Prompts | Successes | Failures | Success Rate | Avg Confidence |
|-----------|---------|-----------|----------|-------------|----------------|
| **SMB Owner** | 4 | 2 | 2 | **50%** | 0.83 |
| **HR Manager** | 3 | 0 | 3 | **0%** | 0.65 |
| **Project Manager** | 2 | 1 | 1 | **50%** | 0.79 |
| **Accountant** | 0 | — | — | — | — |
| **Supplier Manager** | 0 | — | — | — | — |
| **System Admin** | 0 | — | — | — | — |

### By User Group × Language

| User Group | nb | nn | en | de | fr | es | pt |
|-----------|-----|-----|-----|-----|-----|-----|-----|
| SMB Owner | 1✓ | — | — | 2✓ | 1✗ | — | — |
| HR Manager | 1✗ | 1✗ | 1✗ | — | — | — | — |
| Project Manager | 1✗ | 1✓ | — | — | — | — | — |
| Accountant | — | — | — | — | — | — | — |
| Supplier Manager | — | — | — | — | — | — | — |
| System Admin | — | — | — | — | — | — | — |

✓ = success, ✗ = failure

### By User Group × Task Type × Outcome

| User Group | Task Type | Tier | Lang | Outcome | Root Cause |
|-----------|-----------|------|------|---------|------------|
| SMB Owner | CREATE_INVOICE | T1 | nb | ✓ SUCCESS | — |
| SMB Owner | CREATE_PRODUCT | T1 | de | ✓ SUCCESS | Check 4 initially failed (VAT), later fixed |
| SMB Owner | CREATE_CUSTOMER | T1 | de | ✓ SUCCESS | — |
| SMB Owner | INVOICE_WITH_PAYMENT | T2 | fr | ✗ FAILED | **Misclassification** (→ REGISTER_PAYMENT). Narrative prompt + French confused classifier |
| HR Manager | CREATE_DEPARTMENT | T1 | nn | ✗ FAILED | DNS error (infra, not logic) |
| HR Manager | CREATE_DEPARTMENT (batch) | T1 | en | ✗ FAILED | **Batch detection failure**: Gemini returned list, parser crashed → UNKNOWN |
| HR Manager | CREATE_EMPLOYEE | T1 | nb | ✗ FAILED | **Missing field**: startDate required by API but not sent |
| Project Manager | PROJECT_WITH_CUSTOMER | T2 | nn | ✓ SUCCESS | — |
| Project Manager | PROJECT_WITH_CUSTOMER | T2 | nb | ✗ FAILED | 401 (expired token — infra issue) |

---

## 4. User Group Mental Models vs. Our Agent

### SMB Owner (Daglig leder)
**Mental model:** "I describe a business situation and expect the system to handle it end-to-end."
- Uses **narrative prompts** ("Kunden X har en utestående faktura på Y kr... Registrer innbetalingen")
- Expects **compound operations** handled atomically (create customer → create invoice → register payment)
- Provides org numbers, addresses, amounts, VAT info as contextual details
- **Implicit expectation:** "I shouldn't need to know whether a customer exists or not — just handle it"

**Where we fail:** Narrative compound prompts get misclassified. The classifier sees "register payment" and stops, missing the implicit "create invoice first" step. This is worst in non-Norwegian languages (French example).

**Impact:** MEDIUM-HIGH. SMB Owner tasks span T1 (×1) and T2 (×2). INVOICE_WITH_PAYMENT at T2 is high-value.

### HR Manager (Personalansvarlig)
**Mental model:** "I'm onboarding employees and managing organizational structure."
- Uses **direct imperative prompts** ("Opprett en ansatt...", "Create three departments...")
- Expects **batch operations** to work naturally
- Expects **reasonable defaults** (startDate = today if not specified)
- Expects **mixed-language date formats** to parse correctly ("født 4. May 1986")
- **Implicit expectation:** "The API details (required fields, formats) are the system's problem, not mine"

**Where we fail:**
1. **Missing required API fields** (startDate on employee creation) — we don't default intelligently
2. **Batch operations** crashed the parser entirely → UNKNOWN → 0 points
3. **0% success rate** — worst of any user group

**Impact:** HIGH. 10 task types, all T1-T2, but T1 tasks are foundational (CREATE_EMPLOYEE: 10 points with role = 50% of score). Every HR failure is a guaranteed 0.

### Project Manager (Prosjektleder)
**Mental model:** "I'm setting up projects with customer linkages and team assignments."
- Uses **structured prompts** with explicit customer + PM references
- Expects project → customer linkage to work atomically
- Expects PM search/creation if PM doesn't exist
- **Implicit expectation:** "I name the project manager and their email — find or create them"

**Where we fail:** Only infra failures (expired tokens). Logic works well for this group.

**Impact:** LOW currently. PROJECT_WITH_CUSTOMER at T2 is working. Future risk: LOG_HOURS, PROJECT_BILLING untested from grader.

### Accountant (Regnskapsfører)
**Mental model:** "I'm performing period-end accounting tasks — reconciliation, corrections, year-end closing."
- Expects **domain-specific operations** (voucher postings that balance, reconciliation against bank statements)
- Expects **file-based input** (CSV bank transactions)
- Expects **double-entry integrity** (debits = credits)
- **Implicit expectation:** "The system understands accounting principles, not just API calls"

**Where we fail:** **ENTIRELY UNTESTED FROM GRADER.** 4 out of 5 accountant tasks are Tier 3 (×3 multiplier). This is the highest-value blind spot.

**Impact:** CRITICAL. 4 Tier-3 tasks × ×3 multiplier × up to 6 points each = potentially 24 points at stake. Zero grader validation.

### Supplier Manager (Innkjøpsansvarlig)
**Mental model:** "I'm managing vendor relationships and recording incoming invoices."
- Expects supplier creation + invoice registration as separate flows
- Expects "leverandørfaktura" to route to supplier invoice, NOT general invoice
- **Implicit expectation:** "Supplier invoice and customer invoice are completely different workflows"

**Where we fail:** REGISTER_SUPPLIER_INVOICE was just added (this session). CREATE_SUPPLIER_INVOICE exists at T2 but is untested from grader. Risk of "leverandørfaktura" routing to CREATE_INVOICE if anti-keywords miss.

**Impact:** MEDIUM. Supplier tasks span T2-T3. REGISTER_SUPPLIER_INVOICE at T3 is high-value but untested.

### System Admin (Systemansvarlig)
**Mental model:** "I'm configuring company modules and features."
- Single task type (ENABLE_MODULE)
- Expects module name to be extracted and the correct API call made
- **Implicit expectation:** "Just turn it on"

**Where we fail:** Untested from grader. Was previously misclassified as CREATE_PROJECT; anti-keywords now prevent this. Executor may not have correct API calls for module enablement.

**Impact:** MEDIUM. Single T3 task but ×3 multiplier = up to 6 points.

---

## 5. Which User Group We Serve WORST

### Ranking (worst → best)

| Rank | User Group | Evidence | Score Potential at Risk |
|------|-----------|----------|----------------------|
| **1 (WORST)** | **Accountant** | 0 grader tests, 4 Tier-3 tasks (×3), most complex domain logic, likely weakest executor implementations | ~24 pts (4 × T3 × 6 max) |
| **2** | **HR Manager** | 0% success rate on 3 grader tests, missing API field defaults, broken batch ops | ~20 pts (10 tasks × T1/T2) |
| **3** | **Supplier Manager** | 0 grader tests, new task type just added, anti-keyword dependencies | ~16 pts (5 T2 + 1 T3) |
| **4** | **System Admin** | 0 grader tests, single T3 task, executor likely incomplete | ~6 pts (1 × T3 × 6 max) |
| **5** | **SMB Owner** | 50% success rate, compound prompt misclassification in non-Norwegian | ~20 pts (5 T1 + 5 T2) |
| **6 (BEST)** | **Project Manager** | 50% success rate but failures were infra, not logic; well-tested | ~18 pts (1 T1 + 7 T2) |

### Why Accountant is #1 Worst

1. **Highest multiplier exposure:** 4 of 5 tasks are Tier 3 (×3). A single fix here is worth 3× a Tier 1 fix.
2. **Domain complexity:** Accountant tasks require understanding double-entry bookkeeping, reconciliation logic, and period closing — not just CRUD API calls.
3. **File-based input:** BANK_RECONCILIATION likely comes with a CSV attachment. Our file parsing may be untested.
4. **Zero validation:** We have no grader feedback on any accountant task. Every assumption is unverified.
5. **Executor risk:** YEAR_END_CLOSING and BANK_RECONCILIATION executors may be stub implementations or have wrong API calls.

---

## 6. What It Would Take to Improve

### Accountant (Priority 1 — highest ROI)

| Action | Effort | Expected Point Gain |
|--------|--------|-------------------|
| Verify BANK_RECONCILIATION executor against sandbox API | 2h | 3-6 pts (T3) |
| Verify ERROR_CORRECTION executor — does it actually reverse/correct vouchers? | 2h | 3-6 pts (T3) |
| Verify YEAR_END_CLOSING executor — does it call the right API endpoints? | 1h | 3-6 pts (T3) |
| Test CREATE_DIMENSION_VOUCHER with real dimension values | 2h | 3-6 pts (T3) |
| Test REVERSE_PAYMENT end-to-end flow | 1h | 2-4 pts (T2) |
| Add CSV file parsing for bank reconciliation transactions | 3h | 3-6 pts (T3) |

**Total potential: 14-34 points** from a group with zero current grader coverage.

### HR Manager (Priority 2 — immediate failures to fix)

| Action | Effort | Expected Point Gain |
|--------|--------|-------------------|
| Add startDate default (today) to CREATE_EMPLOYEE executor | 15min | 5-10 pts (T1, fixes 422 error) |
| Fix batch department creation (already fixed?) | 30min | 3-7 pts (T1 per dept) |
| Test RUN_PAYROLL executor end-to-end | 2h | 2-4 pts (T2) |
| Verify SET_EMPLOYEE_ROLES handles inline role assignment | 1h | 5 pts (role = 50% of employee score) |
| Test mixed-language date parsing ("4. May 1986") | 30min | 1-2 pts (birth date field) |

**Total potential: 16-28 points** — many are quick fixes for currently-failing grader tests.

### Supplier Manager (Priority 3)

| Action | Effort | Expected Point Gain |
|--------|--------|-------------------|
| Verify REGISTER_SUPPLIER_INVOICE executor end-to-end | 1h | 3-6 pts (T3) |
| Ensure "leverandørfaktura" never routes to CREATE_INVOICE | 30min | 3-6 pts (classification correctness) |
| Test CREATE_SUPPLIER with multilingual prompts | 1h | 2-4 pts (T2) |

**Total potential: 8-16 points.**

### SMB Owner (Priority 4 — compound prompt reliability)

| Action | Effort | Expected Point Gain |
|--------|--------|-------------------|
| Add more INVOICE_WITH_PAYMENT few-shot examples in fr/de/es/pt | 1h | 2-4 pts (T2 misclassification fix) |
| Fix paid_amount calculation (use API invoice total, not hardcoded 1.25×) | 1h | 1-2 pts (payment amount check) |
| Test narrative-style prompts in all 7 languages | 2h | 2-4 pts (classification robustness) |

**Total potential: 5-10 points.**

---

## 7. Language × User Group Interaction

### Key Finding: Non-Norwegian Languages Amplify Failures

| Language | Confirmed Prompts | Success Rate | Worst User Group Hit |
|----------|------------------|-------------|---------------------|
| nb (Bokmål) | 3 | 33% (1/3) | HR Manager (employee 422) |
| nn (Nynorsk) | 2 | 50% (1/2) | HR Manager (dept DNS) |
| en (English) | 1 | 0% (0/1) | HR Manager (batch UNKNOWN) |
| de (German) | 2 | 100% (2/2) | — |
| fr (French) | 1 | 0% (0/1) | SMB Owner (misclassification) |
| es (Spanish) | 0 | — | — |
| pt (Portuguese) | 0 | — | — |

**German is our best language** — both prompts succeeded (SMB Owner tasks).
**French and English are our worst** — 0% success, amplifying classification and batch handling failures.
**Spanish and Portuguese are untested** — complete blind spots.

### Projected Risk: Accountant + Non-Norwegian

Accountant prompts in French/German/Spanish will have:
- Domain-specific vocabulary (Buchungskorrektur, correction d'écriture, corrección de error)
- File references in unfamiliar patterns
- Period/date formats varying by locale

This is our **single highest-risk combination**: the user group we serve worst × the languages where we fail most.

---

## 8. Summary

| Metric | Value |
|--------|-------|
| Total confirmed grader prompts | 9 |
| Overall grader success rate | 33% (3/9) |
| Worst user group (tested) | HR Manager (0% success) |
| Worst user group (projected) | Accountant (0 tests, highest T3 exposure) |
| Best user group | Project Manager (50%, failures = infra only) |
| Highest ROI improvement | Fix HR Manager basics (startDate, batch) = ~16-28 pts |
| Highest ceiling improvement | Validate Accountant T3 executors = ~14-34 pts |
| Language blind spots | Spanish (0 prompts), Portuguese (0 prompts) |
| User groups with zero grader data | Accountant, Supplier Manager, System Admin |
