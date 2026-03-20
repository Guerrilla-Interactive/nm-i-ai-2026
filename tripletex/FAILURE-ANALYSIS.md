# Tripletex AI Accounting Agent -- Comprehensive Failure Analysis

**Date:** 2026-03-20
**Scope:** All failure modes that can cause point loss in NM i AI 2026 competition
**Files analyzed:** `executor.py`, `classifier.py`, `main.py`, `tripletex_client.py`, `task_types.py`

---

## Scoring Context

Each task is graded on multiple "checks" (typically 5-7). Points are awarded per check passed.
An efficiency multiplier (up to 2x) is applied based on:
- Fewer API calls = higher multiplier
- Each 4xx error counts against the multiplier
- Tier multipliers: T1=1x, T2=2x, T3=3x (applied to base score)

**Total point loss = (checks failed * points_per_check) + efficiency penalty**

---

## 1. Classification Failures

### 1.1 Gemini returns invalid JSON
- **Likelihood:** LOW (response_mime_type="application/json" forces structured output)
- **Impact:** Falls to Claude or keyword fallback; if both fail, UNKNOWN = 0 points
- **Mitigation:** YES -- three-tier fallback (Gemini -> Claude -> keywords), markdown fence stripping
- **Suggested fix:** None needed; fallback chain is solid

### 1.2 Gemini timeout / rate limit
- **Likelihood:** MEDIUM (Gemini cold starts can take 5-10s; competition has 5-min total limit)
- **Impact:** Falls to Claude/keyword fallback; adds latency eating into timeout budget
- **Mitigation:** PARTIAL -- MAX_RETRIES=1 with retry, but no explicit timeout on the Gemini call itself
- **Suggested fix:** Add explicit timeout (e.g., 15s) on the `_call_gemini` executor call; if timeout, skip to fallback immediately instead of waiting

### 1.3 Misclassification: INVOICE_WITH_PAYMENT vs REGISTER_PAYMENT
- **Likelihood:** HIGH -- already observed in grader (request #16: French prompt misclassified)
- **Impact:** 5-7 points lost (wrong task executed entirely)
- **Mitigation:** YES -- fixed after grader log analysis; added disambiguation rules + few-shot examples
- **Suggested fix:** Add more few-shot examples in all 7 languages for this case; the classifier prompt already has rules but the keyword fallback has weaker coverage

### 1.4 Misclassification: CREATE_INVOICE vs INVOICE_EXISTING_CUSTOMER
- **Likelihood:** MEDIUM -- the distinction is whether the customer "already exists" (unknowable from prompt alone)
- **Impact:** LOW -- both executors handle customer lookup/creation, so the outcome is usually the same
- **Mitigation:** YES -- both executors create the customer if not found
- **Suggested fix:** None critical; the executor handles both cases

### 1.5 Batch detection failure
- **Likelihood:** MEDIUM -- already observed (request #8: "Create three departments" -> UNKNOWN)
- **Impact:** 0 points for the entire task (all 3 departments not created)
- **Mitigation:** YES -- fixed; batch parsing now handles Gemini returning a list or `{"batch":[...]}`
- **Suggested fix:** Add keyword-fallback batch detection (e.g., "three departments: X, Y, Z" pattern); currently only Gemini/Claude handle batches, keyword fallback cannot

### 1.6 Keyword fallback fails on ambiguous prompts
- **Likelihood:** MEDIUM -- keyword anti-keywords can block valid matches (e.g., "opprett ansatt" blocked if "rolle" appears in prompt)
- **Impact:** Falls to UNKNOWN = 0 points
- **Mitigation:** PARTIAL -- anti_keywords exist but may be too aggressive
- **Suggested fix:** Review anti_keyword lists; consider scoring-based disambiguation instead of hard blocks

### 1.7 Prompt in unexpected language or mixed languages
- **Likelihood:** LOW -- grader uses 7 specified languages
- **Impact:** Misclassification or poor field extraction
- **Mitigation:** YES -- system prompt covers all 7 languages; keyword patterns cover nb/nn/en/de/fr/es/pt
- **Suggested fix:** None needed

### 1.8 Gemini returns task_type not in TaskType enum
- **Likelihood:** LOW
- **Impact:** Falls to UNKNOWN = 0 points
- **Mitigation:** YES -- `_parse_single` catches ValueError and defaults to UNKNOWN
- **Suggested fix:** None needed

### 1.9 Both Gemini and Claude unavailable (env vars not set)
- **Likelihood:** LOW in production (GEMINI_MODEL should be set on Cloud Run)
- **Impact:** Falls to keyword-only classification with lower accuracy (~0.6 confidence)
- **Mitigation:** YES -- keyword fallback always available
- **Suggested fix:** Ensure GEMINI_MODEL env var is set in deployment

---

## 2. Field Extraction Failures

### 2.1 Name splitting errors
- **Likelihood:** MEDIUM -- names with >2 parts (e.g., "Hans Erik Olsen") may split incorrectly
- **Impact:** 1-2 points (wrong firstName/lastName on employee)
- **Mitigation:** PARTIAL -- `_normalize_fields` splits on first space, puts rest in last_name; but names like "van der Berg" will have first_name="van"
- **Suggested fix:** Handle multi-word last names; use LLM extraction as primary (already does this in Gemini mode)

### 2.2 Date format parsing errors
- **Likelihood:** LOW -- Gemini handles date conversion well
- **Impact:** 1 point per wrong date field
- **Mitigation:** YES -- keyword fallback has regex for DD.MM.YYYY, YYYY-MM-DD, and Norwegian text dates
- **Suggested fix:** Add English month names to text date parser (currently only Norwegian months)

### 2.3 Price with thousand separators
- **Likelihood:** MEDIUM -- "22 550 NOK" or "22.550,00 NOK" formats
- **Impact:** 1-2 points (wrong price on product/invoice)
- **Mitigation:** YES -- `_parse_amount` strips spaces and handles European decimal format
- **Suggested fix:** Verify "1.234,56" (European) vs "1,234.56" (US) disambiguation is correct

### 2.4 Org numbers with spaces/dashes
- **Likelihood:** MEDIUM -- "987 654 321" or "987-654-321"
- **Impact:** 1 point (org number not matched/stored correctly)
- **Mitigation:** PARTIAL -- regex `_RE_ORG_NR` captures digits+spaces, then `.replace(" ", "")` strips spaces; but dashes are not stripped
- **Suggested fix:** Add `.replace("-", "")` to org number extraction

### 2.5 Address parsing failures
- **Likelihood:** MEDIUM -- complex addresses ("Storgata 5, 2. etasje, 3015 Drammen")
- **Impact:** 1-2 points (address fields not populated or wrong)
- **Mitigation:** PARTIAL -- regex captures simple "street, postalcode city" but not multi-line or complex addresses
- **Suggested fix:** Rely on LLM extraction for addresses; keyword fallback regex is too fragile for complex cases

### 2.6 VAT percentage not extracted
- **Likelihood:** MEDIUM -- already observed (request #5: product created with 0% instead of 25%)
- **Impact:** 1-2 points (wrong VAT type on product)
- **Mitigation:** YES -- fixed; vat_percentage extraction regex + dynamic _resolve_vat_type
- **Suggested fix:** Ensure VAT keyword matching covers "Steuersatz", "taux de TVA", etc. in all languages

### 2.7 Invoice line extraction failure (complex patterns)
- **Likelihood:** MEDIUM -- patterns like "10 timer konsulentarbeid a 1200 kr" may not match
- **Impact:** 2-3 points (invoice created with wrong/no lines)
- **Mitigation:** PARTIAL -- multiple regex patterns, but "timer" (hours) without "stk" may not match quantity pattern
- **Suggested fix:** The `_extract_invoice_lines` in main.py has a "timer/hours" pattern but classifier.py does not. Ensure consistency.

### 2.8 Product name includes price text
- **Likelihood:** LOW -- LLM usually separates correctly
- **Impact:** 1 point (product name contains "til 2500 kr")
- **Mitigation:** YES -- `_post_process_fields` strips price text from product names
- **Suggested fix:** None needed

### 2.9 Employee identifier parsed as first_name only (single name)
- **Likelihood:** MEDIUM -- prompts like "Slett ansatt Nordmann" (only last name given)
- **Impact:** Employee not found -> task fails -> 0 points
- **Mitigation:** PARTIAL -- `_normalize_fields` puts single-word identifiers in `last_name`, but `_find_employee` searches by firstName primarily
- **Suggested fix:** When employee_identifier is a single word, search both firstName and lastName (requires two API calls or broader search)

---

## 3. API Execution Failures

### 3.1 Customer creation fails (duplicate name)
- **Likelihood:** LOW -- fresh sandbox per submission, unlikely to have pre-existing customers
- **Impact:** Entire invoice/project flow fails -> 0 points for that task
- **Mitigation:** NO -- no duplicate detection; if customer already exists, POST may return 409
- **Suggested fix:** Catch 409 and fall back to searching for the existing customer

### 3.2 Department creation fails (duplicate departmentNumber)
- **Likelihood:** LOW -- but `_ensure_department` hardcodes departmentNumber="1"
- **Impact:** Employee creation may fail (needs department) -> 0 points
- **Mitigation:** NO
- **Suggested fix:** Use a more unique default department number or handle 409 by searching

### 3.3 Employee creation fails (missing required field)
- **Likelihood:** LOW -- email is auto-generated if missing; department is auto-created
- **Impact:** 0 points for the task
- **Mitigation:** YES -- email auto-generation, department auto-creation
- **Suggested fix:** None critical

### 3.4 Order creation fails (no order lines)
- **Likelihood:** MEDIUM -- if line extraction fails, `order_lines` is empty
- **Impact:** Invoice not created -> 0 points
- **Mitigation:** YES -- early return with error message if `not order_lines`
- **Suggested fix:** None needed for the check; fix line extraction (see 2.7)

### 3.5 Invoice creation fails (no bank account)
- **Likelihood:** LOW -- `_ensure_bank_account` sets a default bank account number
- **Impact:** Invoice creation blocked -> 0 points
- **Mitigation:** YES -- proactive bank account setup with hardcoded number "12345678903"
- **Suggested fix:** None needed

### 3.6 Payment registration fails (wrong/missing amount)
- **Likelihood:** HIGH -- no amount validation before API call; `amount=None` passes through
- **Impact:** 4xx error (hurts efficiency) + payment not registered -> lose payment check points
- **Mitigation:** NO -- `_clean` strips None paidAmount, API returns 400
- **Suggested fix:** Add early validation: `if not amount: return error`. Also: fetch invoice total from API to use as default amount.

### 3.7 Payment amount mismatch (VAT calculation wrong)
- **Likelihood:** HIGH for INVOICE_WITH_PAYMENT -- hardcoded 1.25x multiplier for VAT
- **Impact:** 1-2 points (payment amount doesn't match invoice total)
- **Mitigation:** NO -- already identified in EXECUTOR-AUDIT as CRITICAL issues #2 and #3
- **Suggested fix:** Fetch actual invoice total from API response after creation, use that as paidAmount. Or calculate per-line VAT based on actual vatType.

### 3.8 Project creation fails (no project manager)
- **Likelihood:** LOW -- code falls back to first available employee, or creates one
- **Impact:** 0 points if it fails
- **Mitigation:** YES -- multi-level fallback (search by name -> create -> use first employee)
- **Suggested fix:** None critical

### 3.9 Travel expense creation fails (wrong travelDetails fields)
- **Likelihood:** MEDIUM -- field names may not match API schema exactly
- **Impact:** 0 points or partial (expense created but missing details)
- **Mitigation:** NO -- field names not verified against sandbox
- **Suggested fix:** Test against sandbox to verify travelDetails field names

### 3.10 Contact creation fails (customer not found)
- **Likelihood:** LOW -- code creates customer if not found
- **Impact:** Contact created without customer linkage -> may lose 1 check
- **Mitigation:** YES -- auto-creates customer
- **Suggested fix:** None needed

### 3.11 API returns unexpected response format
- **Likelihood:** LOW
- **Impact:** KeyError/TypeError crashes -> 0 points
- **Mitigation:** PARTIAL -- `_extract_value` and `_extract_values` handle standard wrapper; but `.get("id")` on non-dict would crash
- **Suggested fix:** Add defensive checks on response parsing

### 3.12 DELETE returns 403 in sandbox
- **Likelihood:** HIGH for employees (sandbox restrictions)
- **Impact:** Delete not performed -> lose check points
- **Mitigation:** PARTIAL -- employee delete has 403 fallback (mark as contact); travel expense and project deletes do not
- **Suggested fix:** Add 403 handling to delete_travel_expense and delete_project

### 3.13 5xx server errors from Tripletex sandbox
- **Likelihood:** LOW
- **Impact:** Task fails -> 0 points (retry adds latency + extra API call)
- **Mitigation:** YES -- single retry with 1s backoff on 5xx
- **Suggested fix:** None needed

---

## 4. Data Flow Failures

### 4.1 customer_name vs customer_identifier confusion
- **Likelihood:** MEDIUM -- classifier may output either field depending on LLM mood
- **Impact:** Customer not found -> invoice/project fails -> 0 points
- **Mitigation:** YES -- `_find_customer` checks multiple field names: customer_name, customer_identifier, name
- **Suggested fix:** None needed; coverage is comprehensive

### 4.2 employee_identifier doesn't resolve to correct employee
- **Likelihood:** HIGH -- `_find_employee` returns `employees[0]` when lastName doesn't match (EXECUTOR-AUDIT issue #5)
- **Impact:** Wrong employee updated/deleted -> wrong data -> lose all checks
- **Mitigation:** NO -- returns first employee when filter fails
- **Suggested fix:** Return None when lastName is specified but no match found

### 4.3 invoice_identifier doesn't resolve
- **Likelihood:** MEDIUM -- for REGISTER_PAYMENT, the invoice must already exist in the sandbox
- **Impact:** Payment not registered -> 0 points
- **Mitigation:** PARTIAL -- searches by invoiceNumber; but if grader gives invoice by other identifier, lookup fails
- **Suggested fix:** Add fallback: search by customer name if invoice number lookup fails

### 4.4 paid_amount calculation is wrong (mixed ex-VAT and inc-VAT lines)
- **Likelihood:** HIGH -- EXECUTOR-AUDIT critical issue #3
- **Impact:** Payment registered with wrong amount -> lose payment check
- **Mitigation:** NO
- **Suggested fix:** Calculate per-line: sum(ex_vat * 1.25) + sum(inc_vat) separately. Better: use API response to get actual invoice total.

### 4.5 VAT type lookup returns wrong type
- **Likelihood:** MEDIUM -- `typeOfVat: "outgoing"` filter may return empty; hardcoded fallback IDs (3, 6) may be wrong
- **Impact:** 1 point (product has wrong VAT type)
- **Mitigation:** PARTIAL -- dynamic lookup with fallback
- **Suggested fix:** If filtered query returns empty, retry without filter. Remove hardcoded fallback IDs.

### 4.6 project_manager_name not extracted from prompt
- **Likelihood:** MEDIUM -- complex prompts like "Prosjektleiar er Steinar Berge (steinar@example.com)"
- **Impact:** Project created with wrong/default manager -> lose 1 check
- **Mitigation:** PARTIAL -- regex extracts "Prosjektleiar er X Y" pattern; Gemini handles it well
- **Suggested fix:** Ensure keyword fallback also extracts project manager email in parentheses

### 4.7 _normalize_fields drops employee_identifier before executor sees it
- **Likelihood:** LOW -- `_normalize_fields` pops employee_identifier and splits into first_name/last_name
- **Impact:** If splitting fails (single word), only last_name is set; _find_employee may not find by lastName alone (API doesn't support lastName filter)
- **Mitigation:** PARTIAL -- _find_employee has a separate employee_identifier fallback path
- **Suggested fix:** Keep employee_identifier in fields even after normalization, as backup

---

## 5. Edge Case Failures

### 5.1 Sandbox has pre-existing data with conflicting names
- **Likelihood:** LOW -- fresh sandbox per submission
- **Impact:** Duplicate name -> 409 error -> task fails
- **Mitigation:** NO -- no duplicate detection/handling
- **Suggested fix:** Catch 409 errors; fall back to searching for existing entity

### 5.2 Same entity name already exists (from previous batch item)
- **Likelihood:** MEDIUM -- batch operations creating multiple departments could cause unique constraint violations
- **Impact:** 2nd+ items in batch fail -> lose points proportionally
- **Mitigation:** NO -- each batch item executes independently
- **Suggested fix:** Add conflict detection between batch items

### 5.3 Prompt has multiple tasks (non-batch, sequential)
- **Likelihood:** MEDIUM -- "Create customer X and then create an invoice for them"
- **Impact:** Only first task classified and executed -> lose points for second task
- **Mitigation:** PARTIAL -- batch detection exists for same-type tasks; sequential different-type tasks are not handled
- **Suggested fix:** Add multi-step task detection in classifier (e.g., detect "and then" patterns)

### 5.4 Prompt references entities by numeric ID
- **Likelihood:** LOW -- grader typically uses names
- **Impact:** ID not resolved -> entity not found -> task fails
- **Mitigation:** PARTIAL -- some resolvers check for numeric strings (e.g., invoice_identifier)
- **Suggested fix:** Add numeric ID resolution to all entity lookup functions

### 5.5 Timeout (5-min limit)
- **Likelihood:** LOW -- typical task takes 5-15s
- **Impact:** Task not completed -> 0 points
- **Mitigation:** PARTIAL -- 30s timeout per API call; but no overall task timeout
- **Suggested fix:** Add overall task timeout (e.g., 4 minutes) with clean error return

### 5.6 Cold start latency
- **Likelihood:** MEDIUM -- Cloud Run cold starts can add 3-10s
- **Impact:** First request may be slow but should still complete within 5 minutes
- **Mitigation:** YES -- min-instances=1 likely configured
- **Suggested fix:** Verify Cloud Run min-instances configuration

### 5.7 Empty or near-empty prompt
- **Likelihood:** LOW -- grader sends real prompts
- **Impact:** UNKNOWN classification -> 0 points
- **Mitigation:** YES -- returns UNKNOWN with confidence 0.0
- **Suggested fix:** None needed

---

## 6. Scoring Failures (Wrong Data, Not API Errors)

### 6.1 Employee created with wrong userType
- **Likelihood:** MEDIUM -- userType mapping may not cover all grader-used terms
- **Impact:** 1-2 points per employee
- **Mitigation:** YES -- `_USER_TYPE_MAP` covers ADMINISTRATOR->EXTENDED, BEGRENSET->NO_ACCESS, etc.
- **Suggested fix:** Add Norwegian "Utvidet" -> EXTENDED mapping; verify all grader-used terms

### 6.2 Customer created with wrong/missing org number
- **Likelihood:** LOW -- LLM extraction handles org numbers well
- **Impact:** 1 point
- **Mitigation:** YES -- regex and LLM both extract org numbers
- **Suggested fix:** Strip dashes from org numbers (see 2.4)

### 6.3 Product created with wrong price or VAT
- **Likelihood:** MEDIUM -- price field name mismatch (EXECUTOR-AUDIT issue #4: `priceExcludingVatCurrency` vs `priceExcludingVat`)
- **Impact:** 1-2 points
- **Mitigation:** PARTIAL -- uses `priceExcludingVatCurrency` which may or may not be accepted
- **Suggested fix:** Test both field names against sandbox; send whichever works

### 6.4 Invoice created with wrong line items/amounts
- **Likelihood:** MEDIUM -- line extraction regex may fail on complex patterns
- **Impact:** 2-3 points (each wrong line = 1 check failed)
- **Mitigation:** PARTIAL -- multiple regex patterns + LLM extraction
- **Suggested fix:** Ensure "N timer X a Y kr" pattern is covered in classifier.py (currently only in main.py)

### 6.5 Payment registered with wrong amount
- **Likelihood:** HIGH -- VAT calculation issues (see 3.7, 4.4)
- **Impact:** 1-2 points
- **Mitigation:** NO
- **Suggested fix:** Use invoice total from API rather than computing client-side

### 6.6 Project created with wrong customer linkage
- **Likelihood:** LOW -- customer lookup/creation is robust
- **Impact:** 1 point
- **Mitigation:** YES -- both PROJECT_WITH_CUSTOMER and CREATE_PROJECT handle customer lookup
- **Suggested fix:** None needed

### 6.7 Department created with missing/wrong departmentNumber
- **Likelihood:** MEDIUM -- if grader specifies departmentNumber and LLM doesn't extract it
- **Impact:** 1 point
- **Mitigation:** PARTIAL -- regex extraction covers "avdelingsnummer N" and "nummer N" patterns
- **Suggested fix:** Add "Abteilungsnummer", "numero de departamento" patterns

### 6.8 Contact created without customer linkage
- **Likelihood:** LOW -- auto-creates customer if not found
- **Impact:** 1 point (contact not linked to correct customer)
- **Mitigation:** YES
- **Suggested fix:** None needed

### 6.9 Travel expense created with wrong employee
- **Likelihood:** MEDIUM -- employee search may return wrong person (see 4.2)
- **Impact:** 1-2 points
- **Mitigation:** PARTIAL -- falls back to first employee if not found
- **Suggested fix:** Fix _find_employee to not return random employees on mismatch

### 6.10 Invoice created with wrong date
- **Likelihood:** LOW -- LLM handles dates well; executor defaults to today()
- **Impact:** 1 point
- **Mitigation:** YES -- defaults to today's date which is usually acceptable
- **Suggested fix:** None needed

### 6.11 isCustomer flag missing on created customers
- **Likelihood:** MEDIUM -- EXECUTOR-AUDIT issue #9 identified this
- **Impact:** Customer may not appear in customer-specific searches -> downstream tasks fail
- **Mitigation:** PARTIAL -- `_exec_create_customer` includes `isCustomer: True` (line 432), but `_exec_invoice_existing_customer` line 696-699 also sets it; verified present in both
- **Suggested fix:** Already mitigated in main customer creation; verify inline creations also set it

### 6.12 Product created but price field name wrong for API
- **Likelihood:** MEDIUM
- **Impact:** Product has price=0 or null -> invoice line amounts wrong -> cascading failures
- **Mitigation:** NO -- not tested against sandbox
- **Suggested fix:** Test `priceExcludingVatCurrency` vs `priceExcludingVat` on sandbox; use whichever works

---

## Priority Summary

### CRITICAL (Fix immediately -- high likelihood of point loss)

| # | Issue | Likelihood | Impact | Mitigation |
|---|-------|-----------|--------|------------|
| 3.7 | VAT calculation wrong in invoice_with_payment | HIGH | 1-2 pts | NO |
| 4.2 | _find_employee returns wrong employee | HIGH | 0-7 pts | NO |
| 4.4 | paid_amount mixed ex/inc-VAT calculation | HIGH | 1-2 pts | NO |
| 3.6 | Payment amount missing/None not validated | HIGH | 1-2 pts | NO |

### HIGH (Fix before next grader run)

| # | Issue | Likelihood | Impact | Mitigation |
|---|-------|-----------|--------|------------|
| 6.5 | Payment with wrong amount (client-side calc) | HIGH | 1-2 pts | NO |
| 1.5 | Keyword fallback cannot handle batch | MEDIUM | 0-7 pts | NO |
| 6.3 | Product price field name uncertainty | MEDIUM | 1-2 pts | NO |
| 2.4 | Org numbers with dashes not stripped | MEDIUM | 1 pt | NO |
| 5.2 | Batch items conflict with each other | MEDIUM | 1-3 pts | NO |
| 3.12 | DELETE 403 unhandled for travel/project | HIGH | 1-2 pts | PARTIAL |

### MEDIUM (Fix when possible)

| # | Issue | Likelihood | Impact | Mitigation |
|---|-------|-----------|--------|------------|
| 2.1 | Multi-word last names split wrong | MEDIUM | 1-2 pts | PARTIAL |
| 2.7 | Invoice line extraction gaps | MEDIUM | 2-3 pts | PARTIAL |
| 4.5 | VAT type hardcoded fallback IDs | MEDIUM | 1 pt | PARTIAL |
| 2.9 | Single-name employee lookup fails | MEDIUM | 0-7 pts | PARTIAL |
| 5.3 | Multi-step sequential tasks not handled | MEDIUM | 0-7 pts | NO |
| 1.2 | Gemini timeout eats into budget | MEDIUM | latency | PARTIAL |

### LOW (Nice to have)

| # | Issue | Likelihood | Impact | Mitigation |
|---|-------|-----------|--------|------------|
| 3.1 | Duplicate name 409 not handled | LOW | 0-7 pts | NO |
| 5.4 | Entity referenced by numeric ID | LOW | 0-7 pts | PARTIAL |
| 2.2 | English month names not parsed | LOW | 1 pt | NO |
| 6.7 | Department number not extracted (rare langs) | MEDIUM | 1 pt | PARTIAL |

---

## Recommended Fix Order

1. **Fix `_find_employee` fallthrough** -- Return None when lastName specified but no match. Prevents wrong-employee updates/deletes. (4.2)
2. **Fix payment amount calculation** -- Fetch invoice total from API after creation instead of computing client-side with hardcoded 1.25x. Fixes 3.6, 3.7, 4.4, 6.5 all at once.
3. **Add org number dash stripping** -- Simple `.replace("-", "")` in extraction. (2.4)
4. **Add keyword-fallback batch detection** -- Parse "Create N X: A, B, C" patterns. (1.5)
5. **Test product price field names** against sandbox. (6.3, 6.12)
6. **Fix VAT type fallback** -- Retry without `typeOfVat` filter if filtered query returns empty. (4.5)
7. **Add 403 handling to travel expense and project deletes.** (3.12)
8. **Add invoice line "timer/hours" pattern** to classifier.py (currently only in main.py). (2.7, 6.4)
