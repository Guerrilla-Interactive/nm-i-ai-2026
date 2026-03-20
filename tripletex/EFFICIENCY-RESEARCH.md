# Efficiency Bonus Research

> Generated: 2026-03-20
> Goal: Maximize the efficiency bonus (up to 2x tier multiplier) by minimizing API calls and eliminating 4xx errors.

---

## How the Efficiency Bonus Works

From the competition docs:

1. **Only applies to PERFECT correctness (1.0).** Non-perfect submissions get only `correctness x tier`.
2. Two factors determine the bonus:
   - **Call efficiency**: fewer API calls vs. best-known solution = higher bonus
   - **Error cleanliness**: fewer 4xx errors (400, 404, 422) = higher bonus
3. **Score range per task**: 0.0 to `tier_multiplier x 2` (max 2.0 for T1, 4.0 for T2, 6.0 for T3)
4. **Best score tracked per task** -- bad runs never lower your score.
5. **Efficiency benchmarks recalculated every 12 hours** -- if you're the first to achieve minimum calls, you set the benchmark.

### Score Examples (Tier 2, x2 multiplier)

| Scenario | Score |
|----------|-------|
| Failed all checks | 0.0 |
| 80% correct | 1.6 |
| Perfect, many errors/extra calls | ~2.1 |
| Perfect, efficient, few errors | ~2.6 |
| Perfect, best-in-class efficiency, zero errors | **4.0** |

**Key insight**: Getting from ~2.1 to 4.0 (a 90% increase!) is PURELY about efficiency. Correctness is table-stakes; efficiency is the differentiator.

---

## Per-Task API Call Analysis

### Legend

- **Minimum**: theoretical minimum API calls needed
- **Current**: API calls in our executor code (best/worst case)
- **Waste**: calls that could be eliminated

---

## TIER 1 TASKS (x1 multiplier, max score 2.0 each)

### 1. CREATE_EMPLOYEE

**Minimum possible: 1 call** (just POST /employee if we hardcode department ID)
**Current: 1-3 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /department?count=1 | Find default department | MAYBE -- could hardcode if we know the sandbox always has dept id=1, but fresh accounts may not have one |
| POST /department | Create dept if none exist | CONDITIONAL -- only if no dept exists |
| POST /employee | Create employee | YES |

**Optimization opportunities:**
- Fresh sandbox accounts: we don't know if a default department exists. We MUST check or create one. So 2 calls is likely the true minimum (GET dept + POST employee).
- If department_name is specified, that's another GET to find it -- unavoidable.
- **Potential optimization**: Try POST /employee with department: null or without department field -- if the API accepts it, we save 1 call. NEEDS TESTING.
- **Current waste**: None significant. The _ensure_department does 1-2 calls which is near-optimal.

**Current best case: 2 calls** (GET dept + POST employee)
**Current worst case: 3 calls** (GET dept by name fails + GET any dept + POST employee)

### 2. UPDATE_EMPLOYEE

**Minimum possible: 2 calls** (GET employee + PUT employee)
**Current: 2-3 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /employee?firstName=X | Find employee | YES |
| GET /department?name=X | Find new department | CONDITIONAL -- only if changing dept |
| PUT /employee/{id} | Update employee | YES |

**Optimization**: Near-optimal. The department lookup only happens if changing department.

### 3. DELETE_EMPLOYEE

**Minimum possible: 2 calls** (GET employee + DELETE employee)
**Current: 2-4 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /employee?firstName=X | Find employee | YES |
| DELETE /employee/{id} | Delete | YES |
| PUT /employee/{id} | Fallback on 403 (mark as contact) | CONDITIONAL -- error recovery |

**Risk**: The fallback path on DELETE 403 adds an extra PUT call AND causes a 4xx error (the 403 itself). This hurts both call count AND error cleanliness.

**Optimization**: If DELETE always returns 403 in sandbox, we should skip straight to the PUT fallback to avoid the 403 error penalty. NEEDS TESTING to determine if DELETE ever works.

### 4. SET_EMPLOYEE_ROLES

**Minimum possible: 2 calls** (GET employee + PUT employee)
**Current: 2 calls** -- optimal.

### 5. CREATE_CUSTOMER

**Minimum possible: 1 call** (POST /customer)
**Current: 1 call** -- OPTIMAL.

### 6. UPDATE_CUSTOMER

**Minimum possible: 2 calls** (GET customer + PUT customer)
**Current: 2 calls** -- OPTIMAL.

### 7. CREATE_PRODUCT

**Minimum possible: 1 call** (POST /product with hardcoded vatType id)
**Current: 1-2 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /ledger/vatType?typeOfVat=outgoing | Look up VAT type | ELIMINABLE if we hardcode |
| POST /product | Create product | YES |

**Optimization**: The code already has fallback hardcoded values (id=3 for 25%, id=6 for 0%). If we skip the API lookup and go straight to the fallback, we save 1 call on every CREATE_PRODUCT.

**RECOMMENDATION: HIGH PRIORITY** -- hardcode VAT type IDs instead of looking them up. The fallback IDs (3, 6) are already in the code. Just use them directly. This saves 1 API call per product creation.

### 8. CREATE_INVOICE

**Minimum possible: 4 calls** (POST customer + GET bank account + POST order + PUT order/:invoice)
**Current: 4-6 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /customer?customerName=X | Find existing customer | CONDITIONAL |
| POST /customer | Create customer | CONDITIONAL (if not found) |
| GET /ledger/account?number=1920 | Check bank account | NEEDED (prerequisite) |
| PUT /ledger/account/{id} | Set bank account number | CONDITIONAL (if not already set) |
| POST /order | Create order with lines | YES |
| PUT /order/{id}/:invoice | Invoice the order | YES |

**Optimization opportunities:**
- On fresh accounts, customer never exists. Skip the GET /customer search and go straight to POST /customer. Save 1 call.
- Bank account check: On fresh accounts, the bank account number is likely NOT set. We could skip the GET and go straight to a PUT with the known account -- but we need the account ID and version. So GET is unavoidable.
- **RECOMMENDATION**: If customer_name is provided but no customer_id, just POST /customer directly instead of searching first. The grader expects the customer to be created. Save 1 call.

**Current best case: 4 calls** (POST customer + GET bank + POST order + PUT order/:invoice)
**Current worst case: 6 calls** (GET customer + POST customer + GET bank + PUT bank + POST order + PUT order/:invoice)

### 9. CREATE_DEPARTMENT

**Minimum possible: 1 call** (POST /department)
**Current: 1 call** -- OPTIMAL.

### 10. CREATE_PROJECT

**Minimum possible: 2 calls** (GET employee + POST project)
**Current: 2-5 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /employee?firstName=X | Find project manager | YES (manager is required) |
| GET /department?count=1 | For creating manager if needed | CONDITIONAL |
| POST /employee | Create manager if not found | CONDITIONAL |
| GET /customer?customerName=X | Find customer | CONDITIONAL |
| POST /project | Create project | YES |

**Optimization**: When the task specifies a project manager by name and they don't exist, the code creates them (3 extra calls: GET dept + POST employee). This is correct behavior for fresh accounts. For efficiency, if we could assume the first employee is always the manager, we'd save 1 call, but we'd lose correctness.

**Current best case: 2 calls** (GET employee + POST project)
**Current worst case: 5 calls** (GET emp + GET dept + POST emp + GET customer + POST project)

---

## TIER 2 TASKS (x2 multiplier, max score 4.0 each)

### 11. INVOICE_EXISTING_CUSTOMER

**Minimum possible: 4 calls** (GET customer + GET bank + POST order + PUT order/:invoice)
**Current: 4-7 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /customer?customerName=X | Find customer | YES |
| POST /customer | Create if not found | CONDITIONAL |
| GET /ledger/account?number=1920 | Bank account check | YES |
| PUT /ledger/account/{id} | Set bank account | CONDITIONAL |
| POST /order | Create order | YES |
| PUT /order/{id}/:invoice | Invoice order | YES |

**Issue**: This handler calls _exec_create_invoice which may search for customer AGAIN. The flow is: _find_customer (1 call) -> set customer_id -> _exec_create_invoice -> skips customer search (has ID) -> _ensure_bank_account (1-2 calls) -> POST order -> PUT order/:invoice. Actually it's reasonably efficient.

**Current best case: 4 calls** (GET customer + GET bank + POST order + PUT /:invoice)

### 12. REGISTER_PAYMENT

**Minimum possible: 2 calls** (GET invoice + PUT invoice/:payment)
**Current: 2-3 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /invoice?invoiceNumber=X | Find invoice | CONDITIONAL (if no ID) |
| GET /invoice/paymentType | Get payment type | ELIMINABLE if hardcoded |
| PUT /invoice/{id}/:payment | Register payment | YES |

**Optimization**: Hardcode payment type ID. On fresh sandbox, payment types are standard. If we cached the first lookup result, subsequent calls would be free. But since each submission is a fresh account, caching doesn't help across submissions.

**RECOMMENDATION**: Hardcode payment_type_id to avoid the GET /invoice/paymentType call. NEEDS TESTING to determine the standard payment type ID on fresh accounts.

### 13. CREATE_CREDIT_NOTE

**Minimum possible: 2 calls** (GET invoice + PUT invoice/:createCreditNote)
**Current: 2 calls** -- OPTIMAL (when invoice_number is provided)

### 14. INVOICE_WITH_PAYMENT

**Minimum possible: 4 calls** (POST customer + GET bank + POST order + PUT order/:invoice with payment params)
**Current: 5-7 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /customer?customerName=X | Find customer | ELIMINABLE on fresh account |
| POST /customer | Create customer | YES (fresh account) |
| GET /ledger/account?number=1920 | Bank check | YES |
| PUT /ledger/account/{id} | Set bank account | CONDITIONAL |
| GET /invoice/paymentType | Get payment type | ELIMINABLE if hardcoded |
| POST /order | Create order | YES |
| PUT /order/{id}/:invoice | Invoice with payment | YES |

**Optimization**: This is a HIGH VALUE target (T2, max 4.0).
1. Skip customer search on fresh accounts -- just POST directly. Save 1 call.
2. Hardcode payment type ID. Save 1 call.
3. These two optimizations could save 2 calls, potentially going from 6 to 4 calls.

### 15. CREATE_TRAVEL_EXPENSE

**Minimum possible: 2 calls** (GET employee + POST travelExpense)
**Current: 2-4+ calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /employee?firstName=X | Find employee | YES |
| POST /travelExpense | Create expense | YES |
| GET /travelExpense/paymentType | For cost lines | CONDITIONAL |
| POST /travelExpense/cost | Add cost line | CONDITIONAL (per cost) |

**Optimization**: If no costs, it's 2 calls (optimal). With costs, the payment type lookup adds 1 call. Could hardcode travel expense payment type ID.

### 16. DELETE_TRAVEL_EXPENSE

**Minimum possible: 2 calls** (GET travelExpense + DELETE travelExpense)
**Current: 2 calls** -- OPTIMAL.

### 17. CREATE_CONTACT

**Minimum possible: 2 calls** (GET customer + POST contact)
**Current: 2-3 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /customer?customerName=X | Find customer | YES |
| POST /customer | Create if not found | CONDITIONAL |
| POST /contact | Create contact | YES |

**Optimization**: On fresh accounts, customer doesn't exist. Skip search, just POST customer directly. But the task says "for existing customer" so we should search first. The contact task is ambiguous -- depends on whether the grader tests with pre-existing customers or not.

### 18. PROJECT_WITH_CUSTOMER

**Minimum possible: 3 calls** (GET/POST customer + GET employee + POST project)
**Current: 3-6 calls**

This chains _find_customer -> _exec_create_project. Same optimizations as individual tasks.

### 19. FIND_CUSTOMER

**Minimum possible: 1 call** (GET /customer with search params)
**Current: 1 call** -- OPTIMAL.

### 20. UPDATE_PROJECT

**Minimum possible: 2-3 calls** (GET projects + GET project/{id} + PUT project/{id})
**Current: 3 calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /project?name=X | Find project by name | YES |
| GET /project/{id} | Get full project details + version | YES (need version for PUT) |
| PUT /project/{id} | Update | YES |

**Optimization**: Could the search GET return version info? If we add `fields=*` to the search, we might get version in the list response, eliminating the need for the individual GET. Save 1 call.

**RECOMMENDATION**: Add `fields=*` to the GET /project search params. If it returns version, skip the individual GET /project/{id}.

### 21. DELETE_PROJECT

**Minimum possible: 2 calls** (GET project + DELETE project)
**Current: 2 calls** -- OPTIMAL.

### 22. PROJECT_BILLING

**Minimum possible: 5 calls** (GET project + GET bank + POST order + PUT order/:invoice + customer from project)
**Current: 5-8 calls**

This chains: GET project -> get customer from project -> _exec_create_invoice flow. Complex but necessary.

---

## TIER 3 TASKS (x3 multiplier, max score 6.0 each)

### 23. BANK_RECONCILIATION

**Minimum possible: 2-3 calls** (GET ledger/account + POST bank/reconciliation + optional vouchers)
**Current: 2-10+ calls**

This is highly variable. The code tries multiple approaches with error recovery, which is necessary for correctness but hurts efficiency.

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /ledger/account?number=1920 | Find bank account | YES |
| GET /ledger/account?isBankAccount=true | Fallback search | ONLY if first fails -- causes wasted call |
| PUT /ledger/account/{id} | Set bank account number | CONDITIONAL |
| POST /bank/reconciliation | Create reconciliation | YES |
| GET /ledger/account?number=X | Per-transaction counter account | PER TRANSACTION |
| POST /ledger/voucher | Per-transaction voucher | PER TRANSACTION |
| GET /bank/statement | Fallback check | CONDITIONAL |

**Optimization**: This is the HIGHEST VALUE optimization target (T3, max 6.0).
1. The fallback GET /ledger/account?isBankAccount=true (line 178) adds a call when the first search fails. Could be eliminated if we're confident account 1920 exists.
2. Per-transaction counter account lookups are expensive. Hardcode common accounts: 3000 (revenue), 6300 (expense).
3. Minimize voucher creation -- create one voucher with multiple postings instead of one voucher per transaction.

### 24. ERROR_CORRECTION

**Minimum possible: 2 calls** (GET voucher + PUT voucher/:reverse)
**Current: 2-6+ calls**

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /ledger/voucher/{id} | Find voucher | YES |
| GET /ledger/voucher?number=X | Fallback search | ONLY if first fails (404 error!) |
| PUT /ledger/voucher/{id}/:reverse | Reverse | YES |
| DELETE /ledger/voucher/{id} | Fallback if reverse fails | ONLY if reverse fails (error!) |
| GET /ledger/posting?voucherId=X | Get postings for manual reversal | ONLY if both fail |
| POST /ledger/voucher | Create correction | CONDITIONAL |

**CRITICAL ISSUE**: The error recovery chain (reverse fails -> delete fails -> manual reversal) generates multiple 4xx errors that DESTROY the efficiency bonus. Each failed attempt is both an extra call and a counted error.

**RECOMMENDATION HIGH PRIORITY**: Determine which approach works in the sandbox (reverse vs delete vs manual) and go straight to the working one. Eliminate trial-and-error.

### 25. YEAR_END_CLOSING

**Minimum possible: 3-5 calls**
**Current: 3-10+ calls**

Multiple approach cascade with extensive error recovery. Same problem as ERROR_CORRECTION -- each failed approach generates 4xx errors.

| Approach | Calls | Error risk |
|----------|-------|------------|
| Annual account approach | GET annual accounts + PUT :close | 2 calls if it works |
| PUT fallback | GET + PUT annual account | 2-3 calls, may 4xx |
| Voucher approach | GET voucher types + 2x GET ledger accounts + GET postings + POST voucher | 5 calls |
| Close group fallback | GET close group | 1 more call |

**RECOMMENDATION**: Test which approach works in sandbox and hardcode the winning path.

### 26. ENABLE_MODULE

**Minimum possible: 1 call** (GET modules, if already enabled) or **2 calls** (GET + PUT)
**Current: 2 calls** -- near-optimal.

| Call | Purpose | Needed? |
|------|---------|---------|
| GET /company/modules | Get current state | YES |
| PUT /company/modules | Enable module | CONDITIONAL (skip if already enabled) |

**Optimization**: Already good. The already-enabled check saves a PUT call.

---

## PRIORITY OPTIMIZATION MATRIX

Sorted by impact (tier multiplier x calls saved):

| Priority | Task | Tier | Current | Target | Calls Saved | Score Impact |
|----------|------|------|---------|--------|-------------|-------------|
| **1** | CREATE_PRODUCT | T1 | 2 | 1 | 1 | Low (T1 x1) but EASY win |
| **2** | INVOICE_WITH_PAYMENT | T2 | 6 | 4 | 2 | HIGH (T2 x2) |
| **3** | ERROR_CORRECTION | T3 | 2-6 | 2 | 0-4 | VERY HIGH (T3 x3) but mainly error elimination |
| **4** | CREATE_INVOICE | T1 | 5-6 | 4 | 1-2 | Medium |
| **5** | REGISTER_PAYMENT | T2 | 3 | 2 | 1 | Medium (T2 x2) |
| **6** | BANK_RECONCILIATION | T3 | 3-10+ | 3 | 0-7 | VERY HIGH if we can reduce |
| **7** | YEAR_END_CLOSING | T3 | 3-10 | 3-5 | 0-5 | VERY HIGH if we pick right approach |
| **8** | UPDATE_PROJECT | T2 | 3 | 2 | 1 | Medium |
| **9** | CREATE_EMPLOYEE | T1 | 2-3 | 2 | 0-1 | Low |
| **10** | INVOICE_EXISTING_CUSTOMER | T2 | 4-7 | 4 | 0-3 | HIGH |

---

## ERROR PREVENTION ANALYSIS

### Sources of 4xx Errors in Our Code

#### 400 Bad Request
- **Cause**: Missing required fields, wrong field types, invalid enum values
- **Where**: POST /employee missing startDate (seen in grader log!), wrong userType value
- **Prevention**: Validate all required fields before calling API. Always include dateOfBirth, startDate for employees.

#### 403 Forbidden
- **Cause**: DELETE /employee often returns 403 in sandbox
- **Where**: _exec_delete_employee attempts DELETE, gets 403, then falls back to PUT
- **Prevention**: Skip DELETE and go straight to PUT fallback if we know DELETE never works
- **Impact**: 1 wasted call + 1 counted error per delete attempt

#### 404 Not Found
- **Cause**: Searching for entities that don't exist on fresh accounts
- **Where**: GET /ledger/voucher/{id} in ERROR_CORRECTION when ID doesn't match
- **Prevention**: Validate identifiers before API calls. Prefer search endpoints over direct ID lookups.

#### 422 Validation
- **Cause**: Missing required fields the API demands but we didn't include
- **Where**: POST /employee without proper startDate (seen in grader log!)
- **Prevention**: Include all required fields even if the prompt doesn't mention them. Use safe defaults.

### Known 422 Traps from Grader Logs
1. **Employee startDate**: The Tripletex API sometimes requires startDate even though it's not documented as required. Include it as a default (today's date).
2. **Version field**: All PUT operations require version for optimistic locking. Always fetch the entity first to get the version.
3. **Email immutability**: Employee email cannot be changed via PUT. Always pass the existing email value.

---

## CONCRETE OPTIMIZATION RECOMMENDATIONS

### Quick Wins (minimal risk, high impact)

1. **Hardcode VAT type IDs** -- Skip GET /ledger/vatType entirely.
   - 25% standard: id=3
   - 0% exempt: id=6
   - Saves 1 call on every CREATE_PRODUCT (and avoids the rare VAT lookup failure)

2. **Hardcode common ledger account IDs** -- If we can determine the standard IDs on fresh accounts:
   - Account 1920 (bank): need to discover ID once
   - Account 3000 (revenue): for bank reconciliation
   - Account 6300 (expense): for bank reconciliation

3. **Skip customer search on fresh accounts** -- For CREATE_INVOICE and INVOICE_WITH_PAYMENT, the customer never exists on a fresh account. Go straight to POST /customer.

### Medium Effort (some risk, high impact)

4. **Eliminate trial-and-error in error recovery paths**:
   - ERROR_CORRECTION: Test which approach works (reverse vs delete) and use only that one
   - YEAR_END_CLOSING: Test which approach works and hardcode it
   - DELETE_EMPLOYEE: Test if DELETE ever works; if not, skip straight to PUT fallback

5. **Cache payment type IDs in-memory per submission**:
   - GET /invoice/paymentType -- cache result for REGISTER_PAYMENT and INVOICE_WITH_PAYMENT
   - GET /travelExpense/paymentType -- cache for CREATE_TRAVEL_EXPENSE costs

6. **Add `fields=*` to search GETs** to get version numbers in list responses, potentially eliminating follow-up GET-by-ID calls (especially for UPDATE_PROJECT).

### Aggressive (higher risk, highest impact)

7. **Test if department is truly required for employees**: If POST /employee works without a department ref, we can skip the department lookup entirely. Save 1 call on every CREATE_EMPLOYEE.

8. **Test if bank account setup can be done once per submission**: If multiple invoice tasks come in, the bank account only needs to be set up once. Add a flag to the client to track "bank_account_configured" and skip on subsequent calls.

9. **Batch order lines in POST /order**: Already doing this (orderLines in the POST body). Verify there's no per-line API call being made.

---

## FRESH ACCOUNT IMPLICATIONS

Every submission gets a fresh, empty Tripletex sandbox. This means:

| Entity | Exists on Fresh Account? | Implication |
|--------|-------------------------|-------------|
| Employees | NO (except maybe admin) | Must create before referencing |
| Customers | NO | Must create before invoicing |
| Departments | MAYBE (need to test) | May need to create for employees |
| Products | NO | Must create if referenced |
| Invoices | NO | Cannot search for existing |
| VAT Types | YES (system-level) | Can be looked up or hardcoded |
| Ledger Accounts | YES (chart of accounts) | 1920 exists but needs bank number set |
| Payment Types | YES (system-level) | Can be looked up or hardcoded |

**Key insight**: On fresh accounts, "find or create" patterns always end up creating. The "find" step is a wasted call. For tasks where we KNOW the entity doesn't exist (customers, employees on fresh accounts), skip the search.

**HOWEVER**: The grader may send tasks that reference entities created by EARLIER tasks in the same submission. If a submission sends multiple tasks sequentially, a customer created in task 1 would exist for task 2. But each task submission is independent (fresh account), so cross-task references within a single submission are unlikely. The safe assumption: every entity needs to be created.

---

## API CALLS TRACKED BY GRADER

The competition proxy counts ALL API calls that pass through it. This includes:
- Every GET, POST, PUT, DELETE
- Failed calls (4xx, 5xx) count as calls AND as errors
- 5xx retries count as additional calls (our client retries once on 5xx)

The grader does NOT count:
- Internal processing time (LLM calls, parsing, etc.)
- Non-API operations

---

## SUMMARY TABLE: ALL 30 TASK TYPES

| # | Task Type | Tier | Min Calls | Current Best | Current Worst | Key Optimization |
|---|-----------|------|-----------|-------------|---------------|------------------|
| 1 | CREATE_EMPLOYEE | T1 | 2 | 2 | 3 | Test if dept is required |
| 2 | UPDATE_EMPLOYEE | T1 | 2 | 2 | 3 | Near-optimal |
| 3 | DELETE_EMPLOYEE | T1 | 2 | 2 | 4 | Skip DELETE if always 403 |
| 4 | SET_EMPLOYEE_ROLES | T1 | 2 | 2 | 2 | OPTIMAL |
| 5 | CREATE_CUSTOMER | T1 | 1 | 1 | 1 | OPTIMAL |
| 6 | UPDATE_CUSTOMER | T1 | 2 | 2 | 2 | OPTIMAL |
| 7 | CREATE_PRODUCT | T1 | 1 | 1-2 | 2 | Hardcode VAT type ID |
| 8 | CREATE_INVOICE | T1 | 4 | 4 | 6 | Skip customer search |
| 9 | CREATE_DEPARTMENT | T1 | 1 | 1 | 1 | OPTIMAL |
| 10 | CREATE_PROJECT | T1 | 2 | 2 | 5 | Varies by manager availability |
| 11 | INVOICE_EXISTING_CUSTOMER | T2 | 4 | 4 | 7 | Same as CREATE_INVOICE |
| 12 | REGISTER_PAYMENT | T2 | 2 | 2 | 3 | Hardcode payment type ID |
| 13 | CREATE_CREDIT_NOTE | T2 | 2 | 2 | 2 | OPTIMAL |
| 14 | INVOICE_WITH_PAYMENT | T2 | 4 | 4 | 7 | Skip customer search + hardcode payment type |
| 15 | CREATE_TRAVEL_EXPENSE | T2 | 2 | 2 | 4+ | Hardcode payment type for costs |
| 16 | DELETE_TRAVEL_EXPENSE | T2 | 2 | 2 | 2 | OPTIMAL |
| 17 | CREATE_CONTACT | T2 | 2 | 2 | 3 | Depends on customer existence |
| 18 | PROJECT_WITH_CUSTOMER | T2 | 3 | 3 | 6 | Composition of customer + project |
| 19 | FIND_CUSTOMER | T2 | 1 | 1 | 1 | OPTIMAL |
| 20 | UPDATE_PROJECT | T2 | 2 | 3 | 3 | Use search fields=* to skip GET by ID |
| 21 | DELETE_PROJECT | T2 | 2 | 2 | 2 | OPTIMAL |
| 22 | PROJECT_BILLING | T2 | 5 | 5 | 8 | Same as invoice optimizations |
| 23 | BANK_RECONCILIATION | T3 | 2 | 2 | 10+ | Eliminate fallback chains |
| 24 | ERROR_CORRECTION | T3 | 2 | 2 | 6+ | Pick one approach, eliminate errors |
| 25 | YEAR_END_CLOSING | T3 | 3 | 3 | 10 | Pick one approach, eliminate errors |
| 26 | ENABLE_MODULE | T3 | 1-2 | 1-2 | 2 | Near-optimal |

**Tasks already optimal (8):** SET_EMPLOYEE_ROLES, CREATE_CUSTOMER, UPDATE_CUSTOMER, CREATE_DEPARTMENT, CREATE_CREDIT_NOTE, DELETE_TRAVEL_EXPENSE, FIND_CUSTOMER, DELETE_PROJECT.

**Tasks needing optimization (18):** The rest have room for improvement, primarily through hardcoding known IDs and eliminating search-before-create on fresh accounts.

---

## NEXT STEPS

1. **Test in sandbox**: Determine which IDs are stable on fresh accounts (VAT types, payment types, department existence)
2. **Test DELETE /employee**: Does it return 403 always? If so, skip it.
3. **Test error correction approaches**: Which one works? Reverse, delete, or manual?
4. **Test year-end closing approaches**: Which one works?
5. **Test POST /employee without department**: Does it accept null department?
6. **Implement hardcoded IDs**: VAT types, payment types, common ledger accounts
7. **Add bank_account_configured flag**: Skip bank setup on subsequent invoice calls within same submission
