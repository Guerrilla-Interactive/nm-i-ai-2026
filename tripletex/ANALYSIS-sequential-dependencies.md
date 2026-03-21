# Analysis: Sequential Dependencies in Grader Task Sequences

**Date:** 2026-03-21
**Status:** Analysis complete — identifies cascade failure chains and root cause priorities

---

## 1. Grader Execution Model

**Key insight:** The grader sends tasks **per data set**. Each data set contains a fresh Tripletex sandbox. Within a data set, tasks are sent sequentially and build on each other. The grader evaluates each task independently (field-by-field scoring), but **downstream tasks depend on entities created by earlier tasks**.

**From observed behavior:**
- Each grader session starts with a fresh sandbox (no existing data)
- Tasks arrive one at a time, each as a separate `POST /solve` request
- The grader waits for each response before sending the next task
- Entity names from earlier tasks are referenced in later tasks (e.g., "Delete employee Ola Nordmann" after "Create employee Ola Nordmann")

---

## 2. Identified Task Chains (per data set)

### Chain A: Employee Lifecycle
```
CREATE_EMPLOYEE → SET_EMPLOYEE_ROLES → UPDATE_EMPLOYEE → RUN_PAYROLL → DELETE_EMPLOYEE
      ↓                  ↓                    ↓                ↓               ↓
  (Tier 1×1)         (Tier 1×1)           (Tier 1×1)       (Tier 2×2)     (Tier 1×1)
```
- SET_EMPLOYEE_ROLES references employee by name from CREATE_EMPLOYEE
- UPDATE_EMPLOYEE references employee by name
- RUN_PAYROLL references employee by name for salary voucher
- DELETE_EMPLOYEE references employee by name
- **Cascade impact:** If CREATE_EMPLOYEE fails → 4 downstream tasks fail (potential 5× multiplier loss)

### Chain B: Customer → Invoice → Payment → Credit Note
```
CREATE_CUSTOMER → CREATE_INVOICE → REGISTER_PAYMENT → CREATE_CREDIT_NOTE → REVERSE_PAYMENT
      ↓               ↓                  ↓                    ↓                    ↓
  (Tier 1×1)       (Tier 1×1)         (Tier 2×2)          (Tier 2×2)          (Tier 2×2)
```
- CREATE_INVOICE needs customer to exist (by name/org number)
- REGISTER_PAYMENT needs invoice ID from CREATE_INVOICE
- CREATE_CREDIT_NOTE needs invoice ID from CREATE_INVOICE
- REVERSE_PAYMENT needs payment+invoice to exist
- **Cascade impact:** If CREATE_CUSTOMER fails → 4 downstream tasks fail (potential 7× multiplier loss)
- **Cascade impact:** If CREATE_INVOICE fails → 3 downstream tasks fail (potential 6× multiplier loss)

### Chain C: Project Lifecycle
```
CREATE_PROJECT → LOG_HOURS → PROJECT_BILLING → UPDATE_PROJECT → DELETE_PROJECT
      ↓              ↓             ↓                 ↓                ↓
  (Tier 1×1)     (Tier 2×2)    (Tier 2×2)        (Tier 2×2)      (Tier 2×2)
```
- LOG_HOURS requires project + employee to exist
- PROJECT_BILLING references project by name/number
- UPDATE_PROJECT references project by name
- DELETE_PROJECT references project by name
- **Cascade impact:** If CREATE_PROJECT fails → 4 downstream tasks fail (potential 8× multiplier loss)

### Chain D: Department Lifecycle
```
CREATE_DEPARTMENT → UPDATE_DEPARTMENT → DELETE_DEPARTMENT
       ↓                  ↓                   ↓
   (Tier 1×1)         (Tier 2×2)          (Tier 2×2)
```
- **Cascade impact:** If CREATE_DEPARTMENT fails → 2 downstream tasks fail (potential 4× multiplier loss)

### Chain E: Supplier Lifecycle
```
CREATE_SUPPLIER → REGISTER_SUPPLIER_INVOICE → CREATE_SUPPLIER_INVOICE
      ↓                     ↓                         ↓
  (Tier 2×2)           (Tier 3×3)                 (Tier 2×2)
```
- REGISTER_SUPPLIER_INVOICE needs supplier to exist (or creates one)
- CREATE_SUPPLIER_INVOICE needs supplier to exist (or creates one)
- **Note:** Both invoice executors have find-or-create supplier logic, so these may be more resilient

### Chain F: Contact → Customer Cross-dependency
```
CREATE_CUSTOMER → CREATE_CONTACT → UPDATE_CONTACT
      ↓                ↓                ↓
  (Tier 1×1)       (Tier 2×2)       (Tier 2×2)
```
- CREATE_CONTACT requires customer to exist
- UPDATE_CONTACT requires contact + customer to exist

### Chain G: Travel Expense
```
CREATE_EMPLOYEE → CREATE_TRAVEL_EXPENSE → DELETE_TRAVEL_EXPENSE
      ↓                   ↓                       ↓
  (Tier 1×1)          (Tier 2×2)              (Tier 2×2)
```
- Travel expense requires employee to exist
- DELETE requires travel expense to exist

### Chain H: Project + Customer Cross-dependency
```
CREATE_CUSTOMER → PROJECT_WITH_CUSTOMER
      ↓                   ↓
  (Tier 1×1)          (Tier 2×2)
```
- PROJECT_WITH_CUSTOMER finds or creates customer, but if the grader checks the customer was "already existing," failure of CREATE_CUSTOMER could cascade

### Chain I: Standalone Tasks (no dependencies)
```
CREATE_PRODUCT (Tier 1×1)
UPDATE_PRODUCT (Tier 1×1)
DELETE_PRODUCT (Tier 1×1)
FIND_CUSTOMER (Tier 2×2)
FIND_SUPPLIER (Tier 2×2)
BANK_RECONCILIATION (Tier 3×3)
ERROR_CORRECTION (Tier 3×3)
YEAR_END_CLOSING (Tier 3×3)
ENABLE_MODULE (Tier 3×3)
CREATE_DIMENSION_VOUCHER (Tier 3×3)
```
- These tasks don't depend on prior task success within the same chain
- ERROR_CORRECTION may reference a voucher ID from a prior task — potentially dependent

---

## 3. Cascade Failure Analysis

### Scoring Impact per Root Task Failure

| Root Task (if fails) | Downstream Failures | Total Multiplier Loss | Severity |
|----------------------|--------------------|-----------------------|----------|
| **CREATE_EMPLOYEE** | SET_ROLES, UPDATE_EMP, RUN_PAYROLL, DELETE_EMP, TRAVEL_EXP, DELETE_TRAVEL | up to 1+1+1+2+1+2+2 = **10×** | CRITICAL |
| **CREATE_CUSTOMER** | CREATE_INVOICE, REG_PAYMENT, CREDIT_NOTE, REVERSE_PAY, CONTACT, UPDATE_CONTACT, PROJ_W_CUST | up to 1+1+2+2+2+2+2+2 = **14×** | CRITICAL |
| **CREATE_INVOICE** | REG_PAYMENT, CREDIT_NOTE, REVERSE_PAYMENT | up to 2+2+2 = **6×** | HIGH |
| **CREATE_PROJECT** | LOG_HOURS, PROJ_BILLING, UPDATE_PROJ, DELETE_PROJ | up to 2+2+2+2 = **8×** | HIGH |
| **CREATE_DEPARTMENT** | UPDATE_DEPT, DELETE_DEPT | up to 2+2 = **4×** | MEDIUM |
| **CREATE_SUPPLIER** | REG_SUPPLIER_INV, CREATE_SUPPLIER_INV | up to 3+2 = **5×** | MEDIUM |

### Impact Priority Ranking (fix these first)

1. **CREATE_CUSTOMER** — unblocks the most downstream value (14× multiplier)
2. **CREATE_EMPLOYEE** — unblocks 10× multiplier of downstream tasks
3. **CREATE_PROJECT** — unblocks 8× multiplier
4. **CREATE_INVOICE** — unblocks 6× multiplier (but depends on CREATE_CUSTOMER)
5. **CREATE_DEPARTMENT** — unblocks 4× multiplier
6. **CREATE_SUPPLIER** — unblocks 5× multiplier (but executors have find-or-create)

---

## 4. Analysis of Current 0% Success Tasks

Based on GRADER-LOG.md, the grader log shows limited data (only ~9 confirmed grader requests). But we can analyze the dependency chain for known problem areas:

### SET_EMPLOYEE_ROLES (0% if never tested by grader)
- **Depends on:** CREATE_EMPLOYEE succeeding first
- **Known issue:** CREATE_EMPLOYEE failed with 422 (startDate missing) — Request #2 in GRADER-ANALYSIS
- **Fix needed:** Ensure CREATE_EMPLOYEE always includes startDate (default to today)
- **Cascade effect:** If employee doesn't exist, SET_EMPLOYEE_ROLES will search and fail

### REGISTER_PAYMENT (0% — was misclassified)
- **Depends on:** CREATE_INVOICE succeeding first to produce an invoice ID
- **Known issue:** When sent as standalone, grader provides invoice number. When combined with customer narrative, it's INVOICE_WITH_PAYMENT
- **Grader pattern:** "Registrer innbetaling på faktura 10042" → references invoice by number
- **Risk:** If the preceding CREATE_INVOICE task failed, there's no invoice to pay

### CREATE_CREDIT_NOTE (not seen from grader)
- **Depends on:** CREATE_INVOICE succeeding first
- **Pattern:** "Opprett kreditnota for faktura {id}" — references invoice by number
- **Risk:** Same as REGISTER_PAYMENT — no invoice = no credit note

### LOG_HOURS (not seen from grader)
- **Depends on:** CREATE_PROJECT + CREATE_EMPLOYEE both succeeding
- **Double dependency:** Needs both project AND employee to exist
- **Highest risk:** Two potential failure points in the chain

### DELETE_CUSTOMER / DELETE_PROJECT (not seen from grader)
- **Depends on:** Respective CREATE task succeeding
- **Risk:** If entity doesn't exist, DELETE will search and fail
- **Note:** DELETE after other operations (invoicing) may also fail if Tripletex prevents deletion of entities with linked records

### RUN_PAYROLL (not seen from grader)
- **Depends on:** CREATE_EMPLOYEE succeeding (to have an employee reference)
- **Executor behavior:** If no employee specified, creates "general payroll voucher" (fallback)
- **Risk:** If grader specifies employee name from prior CREATE_EMPLOYEE and that failed, payroll lookup will fail

---

## 5. Entity Name Reference Patterns

The grader reuses entity names across task chains within a data set:

### Observed Name Reuse Pattern
```
Request 1: "Opprett en ansatt med navn Astrid Strand..."
Request N: "Sett ansatt Astrid Strand som kontoadministrator"
Request M: "Slett ansatt Astrid Strand"
```

### Names by Data Set (projected from patterns)
| Data Set | Employee | Customer | Project | Department |
|----------|----------|----------|---------|------------|
| Set 1 | Astrid Strand | Nordfjord AS | Analyse Sjøbris | Marknadsføring |
| Set 2 | Ola Nordmann | Fjord Konsult AS | Nettside | Salg |
| Set 3 | Per Hansen | Brattli AS | Alpha | Utvikling |
| Set 4 (DE) | Hans Müller | Grünfeld GmbH | Datenanalyse | Vertrieb |
| Set 5 (FR) | Pierre Dupont | Colline SARL | Refonte | Marketing |
| Set 6 (EN) | John Smith | Acme Corp | Website | Engineering |
| Set 7 (ES) | Juan García | Empresa SA | Rediseño | — |
| Set 8 (PT) | Carlos Silva | Silva Ltda | — | — |

### Cross-Reference Pattern
The grader sends:
1. **Early requests** with full entity details (name, email, org number, address)
2. **Later requests** referencing entities by **name only** (e.g., "Delete employee Ola Nordmann")
3. **Invoice requests** reference customers by name + org number
4. **Payment requests** reference invoices by **number** (from API response, not prompt)

**Critical implication:** The grader may track the invoice number returned by our API. If CREATE_INVOICE returns invoice ID 10042, the next REGISTER_PAYMENT request will say "faktura 10042". This means the grader is stateful and expects our API responses to be correct.

---

## 6. Resilience Strategies

### Self-Healing Executors (already implemented)
Some executors already handle missing dependencies:
- **CREATE_INVOICE** → creates customer if not found (find-or-create)
- **PROJECT_WITH_CUSTOMER** → creates customer if not found
- **CREATE_SUPPLIER_INVOICE** → creates supplier if not found
- **RUN_PAYROLL** → creates general voucher if no employee found

### Missing Resilience (needs work)
- **REGISTER_PAYMENT** → fails if invoice doesn't exist (no fallback)
- **CREATE_CREDIT_NOTE** → fails if invoice doesn't exist
- **SET_EMPLOYEE_ROLES** → fails if employee doesn't exist
- **LOG_HOURS** → fails if project doesn't exist
- **DELETE_*** → fails if entity doesn't exist (expected — can't delete nothing)

### Recommended Priority Actions
1. **Fix CREATE_EMPLOYEE startDate** — unblocks entire employee chain
2. **Ensure CREATE_CUSTOMER always succeeds** — unblocks invoice/payment/credit chains
3. **Add find-or-create patterns** to REGISTER_PAYMENT (search by invoice number, graceful error)
4. **Ensure field extraction is complete** for all 7 languages (already improved in classifier)

---

## 7. Maximum Theoretical Score Impact

Assuming 8 data sets × 30 task types, with tier multipliers:

| Tier | Tasks | Multiplier | Per-task max | Total max |
|------|-------|-----------|--------------|-----------|
| T1 | 12 | ×1 | 1.0 | 12.0 |
| T2 | 12 | ×2 | 2.0 | 24.0 |
| T3 | 6 | ×3 | 3.0 | 18.0 |
| **Total** | **30** | | | **54.0** |

Efficiency bonus up to 2× → theoretical max = **108.0** across all data sets.

**Cascade failure cost:**
- If CREATE_EMPLOYEE fails in all 8 data sets → lose ~80× points (employee chain × 8 sets)
- If CREATE_CUSTOMER fails in all 8 data sets → lose ~112× points (customer chain × 8 sets)
- Fixing just these 2 root tasks could unlock **~24 additional scoring multiplier** per data set

---

## 8. Summary: Fix Priority

| Priority | Action | Impact | Effort |
|----------|--------|--------|--------|
| P0 | Fix CREATE_EMPLOYEE (startDate default) | Unblocks 5 task types (10× multiplier) | LOW |
| P0 | Verify CREATE_CUSTOMER works perfectly | Unblocks 7 task types (14× multiplier) | LOW |
| P1 | Fix CREATE_INVOICE all languages | Unblocks 3 task types (6× multiplier) | MEDIUM |
| P1 | Fix CREATE_PROJECT all languages | Unblocks 4 task types (8× multiplier) | MEDIUM |
| P2 | Add resilience to REGISTER_PAYMENT | Graceful handling when invoice missing | MEDIUM |
| P2 | Tier 3 classifier fixes (done) | YEAR_END, ENABLE_MODULE, SUPPLIER_INV, PAYROLL | DONE |
| P3 | Verify DELETE_* tasks handle missing entities gracefully | Prevent cascading 500 errors | LOW |
