# Tripletex Grader Scoring Research

**Date:** 2026-03-20
**Sources:** Competition docs (challenge://tripletex/*), grader logs, API testing, executor audit
**Goal:** Determine exactly what checks the grader runs for each of the 30 task types

---

## How Scoring Works (Overview)

1. Agent receives prompt + credentials, executes API calls
2. Grader queries the Tripletex API to verify what was created/modified
3. Each task has specific **field-by-field checks** worth different point values
4. `correctness = points_earned / max_points` (0.0 to 1.0)
5. `base_score = correctness x tier_multiplier` (T1=x1, T2=x2, T3=x3)
6. If correctness == 1.0: efficiency bonus can up to **double** the base score
7. If correctness < 1.0: score = `correctness x tier` (no efficiency bonus)
8. Best score per task type is kept forever (bad runs never lower your score)
9. Efficiency benchmarks recalculated every 12 hours
10. **Leaderboard score = sum of best scores across all 30 task types**

### Score Range

| Tier | Max (no bonus) | Max (with bonus) |
|------|---------------|-----------------|
| Tier 1 (x1) | 1.0 | 2.0 |
| Tier 2 (x2) | 2.0 | 4.0 |
| Tier 3 (x3) | 3.0 | 6.0 |

### Efficiency Bonus Factors

- **Call efficiency**: API calls vs. best-known solution (fewer = better)
- **Error cleanliness**: 4xx errors (400, 404, 422) reduce the bonus
- Only applies to PERFECT correctness (1.0)

---

## What We KNOW (from docs + grader results)

### Confirmed: CREATE_EMPLOYEE scoring (from official docs)

| Check | Points |
|-------|--------|
| Employee found | 2 |
| Correct first name | 1 |
| Correct last name | 1 |
| Correct email | 1 |
| Administrator role assigned | 5 |
| **Total** | **10** |

**Key insight:** Admin role = 50% of the score. The grader checks `userType == "EXTENDED"`.

### Confirmed: CREATE_PRODUCT scoring (from grader results)

The grader scored CREATE_PRODUCT out of **7 checks**:
- V6: 5/7 (71%) -- Check 4 failed (vatType was 0% instead of 25%)
- V7: 6/7 (86%) -- Check 4 still failed
- V8: 7/7 (100%) -- vatType fix deployed

Inferred checks for CREATE_PRODUCT:

| Check | Points (likely) | Evidence |
|-------|----------------|---------|
| Product found | 1 | Standard existence check |
| Correct name | 1 | Verified in grader prompt "Datenberatung" |
| Correct product number | 1 | Grader prompt specified "5524" |
| Correct price (excl. VAT) | 1 | Grader prompt specified "22550 NOK ohne MwSt." |
| Correct VAT type/rate | 1 | **Check 4 failed** -- vatType mismatch was the issue |
| Unknown check 6 | 1 | Possibly description, currency, or unit |
| Unknown check 7 | 1 | Possibly another field from the prompt |
| **Total** | **7** | |

### Confirmed: INVOICE_WITH_PAYMENT scoring (from grader results)

Scored 2/7 (29%) when misclassified as REGISTER_PAYMENT.

Inferred checks:

| Check | Points (likely) | Notes |
|-------|----------------|-------|
| Customer found/created | 1 | Must create customer with correct org number |
| Invoice found | 1 | Must create the invoice |
| Correct invoice amount (excl. VAT) | 1 | Matches prompt amount |
| Correct line description | 1 | "Heures de conseil" / "Konsulenttimer" |
| Payment registered | 1 | PUT /invoice/{id}/:payment |
| Correct payment amount | 1 | Must match invoice total incl. VAT |
| Additional check (date/VAT) | 1 | Possibly payment date or VAT rate |
| **Total** | **7** | |

---

## Inferred Scoring for ALL 30 Task Types

The documentation only provides the CREATE_EMPLOYEE example explicitly. The following are **inferences** based on:
- The documented example pattern (entity found + field checks)
- Observed grader scoring (CREATE_PRODUCT = 7 checks, INVOICE_WITH_PAYMENT = 7 checks)
- The structure of grader prompts (what data they include)
- API field structure (what the grader can verify via GET)

### General Pattern

Every task follows this structure:
1. **Entity existence check** (1-2 pts): Did the entity get created/modified/deleted?
2. **Field correctness checks** (1 pt each): Does each field match the expected value?
3. **Special/complex checks** (1-5 pts): Role assignment, linkage, multi-step completion

---

## TIER 1 TASKS (x1 multiplier, max 2.0 with efficiency)

### 1. CREATE_EMPLOYEE (10 checks, CONFIRMED)

| Check | Points | Grader verifies |
|-------|--------|----------------|
| Employee found | 2 | GET /employee -- new employee exists |
| Correct first name | 1 | `firstName` matches prompt |
| Correct last name | 1 | `lastName` matches prompt |
| Correct email | 1 | `email` matches prompt |
| Administrator role assigned | 5 | `userType == "EXTENDED"` |
| **Total** | **10** | |

**Critical:** Admin role is 50% of score. If prompt says "kontoadministrator" / "administrator", must set `userType: "EXTENDED"`.

**Failure modes:**
- Missing `userType: "EXTENDED"` = lose 5/10 points (biggest risk)
- Misclassified as SET_EMPLOYEE_ROLES when prompt contains "rolle" = 0 points
- Name splitting failure (e.g., "Kari Bergstrom" not split into first/last) = lose 2 points
- Email not extracted = lose 1 point
- 422 error from missing/malformed fields = 0 points (entity not created)

### 2. UPDATE_EMPLOYEE (estimated 5-7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct employee found | 2 | GET /employee -- found the right one by name/email |
| Field A updated correctly | 1 | Updated field matches expected value |
| Field B updated correctly | 1 | Updated field matches expected value |
| Field C updated correctly | 1 | Updated field matches expected value |
| No unintended changes | 1 | Other fields unchanged |
| **Total** | **~6** | |

**Failure modes:**
- Wrong employee modified (fuzzy name matching hits wrong person)
- Version mismatch on PUT (forgot to include `version` field)
- Missing `dateOfBirth` on PUT (required for PUT even if null on create)

### 3. DELETE_EMPLOYEE (estimated 3-4 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct employee identified | 2 | Found the right employee to delete |
| Employee deleted | 2 | GET /employee -- employee no longer exists or marked inactive |
| **Total** | **~4** | |

**Failure modes:**
- Wrong employee deleted (name matching)
- Employee not found on fresh account (depends on task setup)
- API returns 403 if employee has linked resources

### 4. SET_EMPLOYEE_ROLES (estimated 5-7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct employee found | 2 | Identified the right employee |
| Role correctly set | 3 | `userType` matches expected value |
| No unintended changes | 1 | Other fields unchanged |
| **Total** | **~6** | |

**Note:** This task modifies an EXISTING employee. On a fresh account, the only employee is the default one created with the sandbox. The grader may pre-populate employees.

### 5. CREATE_CUSTOMER (estimated 7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Customer found | 1 | GET /customer -- new customer exists |
| Correct name | 1 | `name` matches prompt |
| Correct org number | 1 | `organizationNumber` matches |
| Correct address line | 1 | `postalAddress.addressLine1` matches |
| Correct postal code | 1 | `postalAddress.postalCode` matches |
| Correct city | 1 | `postalAddress.city` matches |
| Correct email (if specified) | 1 | `email` matches |
| **Total** | **~7** | |

**Evidence:** Grader prompt "Erstellen Sie den Kunden Grunfeld GmbH mit der Organisationsnummer 835026434. Die Adresse ist Fjordveien 105, 3015 Drammen" includes: name, org number, address, postal code, city.

**Failure modes:**
- Org number not extracted = lose 1 point
- Address parsing failure (e.g., "ist Fjordveien 105" instead of "Fjordveien 105") = lose 1 point
- Missing postal code or city = lose 1-2 points

### 6. UPDATE_CUSTOMER (estimated 5-7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct customer found | 2 | Found by name/org number |
| Field A updated | 1 | Changed field matches expected |
| Field B updated | 1 | Changed field matches expected |
| No unintended changes | 1 | Other fields unchanged |
| **Total** | **~5** | |

**Failure modes:**
- Customer not found (wrong search parameters)
- Version mismatch on PUT
- Address update requires separate address ID handling

### 7. CREATE_PRODUCT (7 checks, PARTIALLY CONFIRMED)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Product found | 1 | GET /product -- new product exists |
| Correct name | 1 | `name` matches |
| Correct product number | 1 | `number` matches |
| Correct price (excl. VAT) | 1 | `priceExcludingVatCurrency` matches |
| Correct VAT type | 1 | `vatType` matches expected rate (25%, 15%, 12%, 0%) |
| Check 6 (unknown) | 1 | Possibly `description`, `currency`, or `unit` |
| Check 7 (unknown) | 1 | Possibly another field |
| **Total** | **7** | |

**Evidence:** Grader scored 5/7, 6/7, 7/7. Check 4 was identified as vatType mismatch.

**Failure modes:**
- Hardcoded vatType ID (IDs vary per sandbox!) = lose 1 point
- Must look up VAT type dynamically via GET /ledger/vatType
- Product number not extracted = lose 1 point
- Wrong price field name (`priceExcludingVat` vs `priceExcludingVatCurrency`)

### 8. CREATE_INVOICE (estimated 7-8 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Customer found/created | 1 | Customer exists with correct name |
| Invoice found | 1 | GET /invoice -- invoice exists |
| Correct line count | 1 | Number of order lines matches |
| Correct line description | 1 | Order line description matches |
| Correct quantity | 1 | Order line count matches |
| Correct unit price | 1 | Price matches prompt |
| Correct total amount | 1 | Total amount matches |
| **Total** | **~7** | |

**Evidence:** Grader prompt "Lag faktura til kunde Nordfjord AS: 2 stk Konsulenttjeneste til 1500 kr" includes: customer name, quantity (2), description (Konsulenttjeneste), unit price (1500 kr).

**Failure modes:**
- Invoice creation requires Order first (POST /order then PUT /order/{id}/:invoice)
- Order line field mapping errors (count vs quantity, unitPriceExcludingVatCurrency)
- Missing deliveryDate on order = 422 error
- Customer not created first = 422 error on order

### 9. CREATE_DEPARTMENT (estimated 3-4 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Department found | 1 | GET /department -- department exists |
| Correct name | 1 | `name` matches |
| Correct department number | 1 | `departmentNumber` matches (if specified) |
| **Total** | **~3** | |

**Failure modes:**
- Batch creation ("Create three departments") -- if not handled, score = 0
- Special characters in names (Marknadsfoering)

### 10. CREATE_PROJECT (estimated 5-7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Project found | 1 | GET /project -- project exists |
| Correct name | 1 | `name` matches |
| Correct project manager | 1 | `projectManager` linked correctly |
| Correct customer link | 1 | `customer` linked (if specified) |
| Correct start/end date | 1 | Dates match (if specified) |
| **Total** | **~5** | |

**Failure modes:**
- Requires at least 1 employee for projectManager (must GET or create)
- If customer specified, must create/find customer first

---

## TIER 2 TASKS (x2 multiplier, max 4.0 with efficiency)

### 11. INVOICE_EXISTING_CUSTOMER (estimated 7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct customer found | 1 | Found existing customer by name/org |
| Invoice found | 1 | Invoice exists |
| Customer linked to invoice | 1 | Invoice customer matches |
| Correct line description | 1 | Order line description |
| Correct quantity | 1 | Order line count |
| Correct unit price | 1 | Price matches |
| Correct total | 1 | Total amount correct |
| **Total** | **~7** | |

**Note:** Customer ALREADY EXISTS in this variant. Grader pre-populates the customer. Agent must find (not create) the customer.

### 12. REGISTER_PAYMENT (estimated 5-6 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct invoice found | 2 | Found the right invoice |
| Payment registered | 1 | Invoice has a payment |
| Correct payment amount | 1 | `paidAmount` matches |
| Correct payment date | 1 | `paymentDate` matches |
| **Total** | **~5** | |

**Failure modes:**
- Invoice doesn't exist yet (may need to create customer + order + invoice first)
- Payment type ID not discovered (must GET /invoice/paymentType first)
- Amount mismatch (excl. vs incl. VAT confusion)

### 13. CREATE_CREDIT_NOTE (estimated 4-5 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Original invoice found | 1 | Identified correct invoice |
| Credit note created | 2 | Credit note exists linked to invoice |
| Correct date | 1 | Credit note date matches |
| **Total** | **~4** | |

### 14. INVOICE_WITH_PAYMENT (7 checks, PARTIALLY CONFIRMED)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Customer created/found | 1 | Customer with correct name/org exists |
| Invoice created | 1 | Invoice exists |
| Correct line description | 1 | Order line matches prompt |
| Correct amount | 1 | Invoice total matches |
| Payment registered | 1 | Payment exists on invoice |
| Correct payment amount | 1 | Payment amount matches invoice total |
| Additional check | 1 | Possibly org number, VAT, or date |
| **Total** | **7** | |

**Evidence:** Grader scored 2/7 when misclassified. The 2 points likely came from customer creation (partially correct).

**Critical flow:** POST /customer -> POST /order -> PUT /order/{id}/:invoice -> PUT /invoice/{id}/:payment

**Failure modes:**
- Misclassified as REGISTER_PAYMENT (only looks for existing invoice)
- VAT calculation error (hardcoded 1.25 multiplier ignores actual VAT rate)
- Mixed price types (ex-VAT + inc-VAT lines) cause wrong total
- Payment amount must match actual invoice total (fetch from API, don't compute client-side)

### 15. CREATE_TRAVEL_EXPENSE (estimated 6-8 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Travel expense found | 1 | GET /travelExpense -- exists |
| Correct employee linked | 1 | `employee` matches |
| Correct title | 1 | `title` matches |
| Correct departure/return dates | 1 | `travelDetails.departureDate/returnDate` match |
| Correct departure/destination | 1 | `travelDetails.departureFrom/destination` match |
| Correct purpose | 1 | `travelDetails.purpose` matches |
| Costs/mileage correct | 1-2 | If prompt includes costs or mileage data |
| **Total** | **~7** | |

**Failure modes:**
- Employee not found (must GET existing employees or create one)
- Travel detail fields are nested (`travelDetails.departureDate`)
- Cost categories and payment types require lookup calls
- Mileage rate types require GET /travelExpense/rate

### 16. DELETE_TRAVEL_EXPENSE (estimated 3-4 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct travel expense identified | 2 | Found by title/employee/date |
| Travel expense deleted | 2 | GET /travelExpense -- no longer exists |
| **Total** | **~4** | |

### 17. PROJECT_WITH_CUSTOMER (estimated 6-7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Customer found/created | 1 | Customer with correct org number exists |
| Project found | 1 | GET /project -- project exists |
| Correct project name | 1 | `name` matches |
| Customer linked to project | 1 | `project.customer.id` = customer's ID |
| Correct project manager | 1 | `projectManager` matches (name/email) |
| Project manager email correct | 1 | Employee with correct email is the PM |
| **Total** | **~6** | |

**Evidence:** Grader prompt "Opprett prosjektet 'Analyse Sjobris' knytt til kunden Sjobris AS (org.nr 883693329). Prosjektleiar er Steinar Berge (steinar@sjobris.no)"

**Critical flow:** POST /customer (with org nr) -> POST /employee (project manager) -> POST /project (link all three)

### 18. PROJECT_BILLING (estimated 6-7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Project found | 1 | Correct project identified |
| Invoice created | 1 | Invoice exists |
| Invoice linked to project | 1 | Project reference on invoice/order |
| Correct line description | 1 | Order line matches |
| Correct amount | 1 | Total matches |
| Customer correct | 1 | Invoice customer = project customer |
| **Total** | **~6** | |

### 19. CREATE_CONTACT (estimated 5-6 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Contact found | 1 | GET /contact -- contact exists |
| Correct first name | 1 | `firstName` matches |
| Correct last name | 1 | `lastName` matches |
| Correct email | 1 | `email` matches |
| Linked to correct customer | 1 | `customer.id` matches |
| **Total** | **~5** | |

**Failure modes:**
- Customer not found (must find existing customer first)
- First/last name not split from full name

### 20. FIND_CUSTOMER (estimated 3-4 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct customer identified | 2 | Found the right customer |
| Return correct data | 1 | Response includes customer info |
| **Total** | **~3** | |

**Note:** This is unusual -- the grader likely checks that the agent performed a GET /customer with correct search params and identified the right entity. May require the agent to return data in its response body.

### 21. UPDATE_PROJECT (estimated 5-6 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct project found | 2 | Found by name/number |
| Field A updated | 1 | Changed field matches |
| Field B updated | 1 | Changed field matches |
| No unintended changes | 1 | Other fields unchanged |
| **Total** | **~5** | |

### 22. DELETE_PROJECT (estimated 3-4 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct project identified | 2 | Found the right project |
| Project deleted | 2 | Project no longer exists or is closed |
| **Total** | **~4** | |

---

## TIER 3 TASKS (x3 multiplier, max 6.0 with efficiency)

### 23. BANK_RECONCILIATION (estimated 7-10 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Bank account identified | 1 | Correct ledger account used |
| Transactions parsed from file | 2 | All transactions from CSV/file extracted |
| Vouchers/postings created | 2 | Correct journal entries in ledger |
| Amounts match | 1 | Each posting amount matches CSV line |
| Postings balanced | 1 | Debit/credit balance to zero |
| Account reconciled | 1 | Bank balance matches ledger |
| **Total** | **~8** | |

**Note:** Requires parsing attached CSV/file. Uses POST /ledger/voucher. Most complex task.

**Failure modes:**
- File not parsed (base64 decoding, CSV parsing)
- Wrong ledger accounts used
- Postings don't balance (must sum to zero)
- Multiple transactions = multiple vouchers

### 24. ERROR_CORRECTION (estimated 5-7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Original voucher found | 1 | Identified incorrect entry |
| Reversal voucher created | 2 | Reverse posting exists |
| Correct voucher created | 2 | New correct posting exists |
| Amounts correct | 1 | Match expected values |
| **Total** | **~6** | |

### 25. YEAR_END_CLOSING (estimated 5-7 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct year identified | 1 | Year parameter matches |
| Closing entries created | 2 | Revenue/expense accounts zeroed |
| Balance carried forward | 2 | Opening balances for new year |
| **Total** | **~5** | |

### 26. ENABLE_MODULE (estimated 2-3 checks)

| Check | Points (est.) | Grader verifies |
|-------|--------------|----------------|
| Correct module identified | 1 | Module name matches |
| Module enabled | 2 | Module is active in company settings |
| **Total** | **~3** | |

---

## REMAINING INFERRED TASK TYPES (27-30)

The docs mention 30 tasks but only ~26 are explicitly named. The remaining 4 are likely variants or combinations we haven't identified. Possible candidates:

27. **CREATE_SUPPLIER** -- Create a supplier/vendor entity
28. **BATCH_CREATE** -- Create multiple entities in one prompt (observed: "Create three departments")
29. **CREATE_EMPLOYEE_WITH_DEPARTMENT** -- Employee creation that requires department creation first
30. **MULTI_INVOICE** -- Create multiple invoices or invoice multiple customers

---

## Key Findings

### 1. Admin Role is the Single Highest-Value Check

At 5/10 points, the admin role check on CREATE_EMPLOYEE is worth more than any other single check we've observed. Missing it cuts your score in half for that task.

### 2. The Grader Verifies via API GET Calls

The grader does NOT check your agent's response body. It queries the Tripletex API directly:
- `GET /employee` to check employees
- `GET /customer` to check customers
- `GET /product` to check products
- `GET /invoice` to check invoices
- etc.

Your response of `{"status": "completed"}` is irrelevant to scoring. What matters is what exists in the Tripletex account after your agent runs.

### 3. Entity Existence is Always Check #1

Every task starts with "Did the entity get created/found?" This is typically worth 1-2 points. If entity creation fails entirely (422 error, wrong endpoint), you score 0.

### 4. VAT Type IDs Are Dynamic

VAT type IDs vary per sandbox instance. Hardcoding `vatType: {"id": 3}` for 25% will fail on some sandboxes. Always look up via `GET /ledger/vatType`.

### 5. Payment Amount Must Match Invoice Total (Including VAT)

For REGISTER_PAYMENT and INVOICE_WITH_PAYMENT, the payment amount must match the invoice total INCLUDING VAT. Don't compute this client-side -- fetch it from the invoice response after creation.

### 6. Field-Level Checks Are Exact String Matches

Based on grader behavior, field checks appear to use exact or near-exact string matching:
- "Grunfeld GmbH" must match exactly (not "Gruenfeld GmbH")
- "Fjordveien 105" must match (not "ist Fjordveien 105")
- Norwegian characters (ae, o, aa) must be preserved

### 7. Batch Tasks Count as One Task Type

"Create three departments" is scored as one task with checks for all three departments. Missing one department costs points on that single task submission.

---

## Scoring Priority Matrix

Tasks ranked by `max_score_with_bonus x probability_of_encountering`:

| Priority | Task Type | Tier | Max Score | Complexity | Notes |
|----------|-----------|------|-----------|------------|-------|
| CRITICAL | CREATE_EMPLOYEE | T1 | 2.0 | Low | Admin role = 5/10 pts |
| CRITICAL | CREATE_CUSTOMER | T1 | 2.0 | Low | Org number + address |
| CRITICAL | CREATE_PRODUCT | T1 | 2.0 | Low | VAT type lookup critical |
| CRITICAL | CREATE_INVOICE | T1 | 2.0 | Medium | Requires order creation |
| CRITICAL | CREATE_DEPARTMENT | T1 | 2.0 | Low | Must handle batch |
| HIGH | INVOICE_WITH_PAYMENT | T2 | 4.0 | High | Multi-step, VAT calc |
| HIGH | PROJECT_WITH_CUSTOMER | T2 | 4.0 | High | 3 entities to create |
| HIGH | CREATE_TRAVEL_EXPENSE | T2 | 4.0 | High | Complex nested fields |
| HIGH | REGISTER_PAYMENT | T2 | 4.0 | Medium | Amount matching |
| HIGH | CREATE_PROJECT | T1 | 2.0 | Medium | Needs employee for PM |
| MEDIUM | CREATE_CONTACT | T2 | 4.0 | Medium | Customer lookup |
| MEDIUM | UPDATE_EMPLOYEE | T1 | 2.0 | Medium | Version management |
| MEDIUM | UPDATE_CUSTOMER | T1 | 2.0 | Medium | Version management |
| MEDIUM | CREATE_CREDIT_NOTE | T2 | 4.0 | Medium | Invoice lookup |
| MEDIUM | DELETE_EMPLOYEE | T1 | 2.0 | Low | Correct ID |
| MEDIUM | DELETE_TRAVEL_EXPENSE | T2 | 4.0 | Medium | Lookup |
| MEDIUM | SET_EMPLOYEE_ROLES | T1 | 2.0 | Low | userType field |
| LOW | BANK_RECONCILIATION | T3 | 6.0 | Very high | File parsing + vouchers |
| LOW | ERROR_CORRECTION | T3 | 6.0 | Very high | Ledger knowledge |
| LOW | YEAR_END_CLOSING | T3 | 6.0 | Very high | Accounting knowledge |
| LOW | ENABLE_MODULE | T3 | 6.0 | Unknown | API unknown |

---

## Recommended Verification Strategy

For each task type, after executing API calls, the agent should verify its own work by:

1. **GET the created entity** to confirm it exists
2. **Check key fields** match what was requested
3. **Log discrepancies** for debugging

This costs extra API calls (hurts efficiency) but ensures correctness, which is worth more than the efficiency bonus on imperfect submissions. Only optimize for efficiency once correctness is 100%.

---

## Open Questions

1. **What are checks 6-7 for CREATE_PRODUCT?** We achieved 7/7 but don't know what all checks verify.
2. **Does the grader pre-populate data?** For REGISTER_PAYMENT, does the grader create the invoice first, or must the agent create everything from scratch?
3. **How does the grader handle batch tasks?** Does "Create three departments" have 3 existence checks + 3 name checks = 6 checks? Or is it a single "all created" check?
4. **What are the exact remaining 4-6 task types?** The docs say 30 but only ~24-26 are enumerable from available information.
5. **Does FIND_CUSTOMER require a specific response format?** Or is it checking that the agent performed the correct API query?
6. **Does the grader check for specific `invoiceDueDate`?** Payment terms may be part of invoice scoring.
7. **For YEAR_END_CLOSING, does the grader pre-populate a full year of transactions?** The task complexity depends heavily on what state the account starts in.
