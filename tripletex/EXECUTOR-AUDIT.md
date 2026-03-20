# Executor Audit Report

**File:** `tripletex/app/executor.py`
**Date:** 2026-03-20
**Auditor:** Claude (automated)

---

## Summary

Audited all 24 executor functions plus helpers for invalid fields, missing required fields, wrong data types, error handling gaps, and logic bugs. Found 19 issues across severity levels.

| Severity | Count |
|----------|-------|
| CRITICAL | 3     |
| HIGH     | 7     |
| MEDIUM   | 6     |
| LOW      | 3     |

---

## Issues Found

### 1. CRITICAL: `_exec_create_employee` -- `start_date` in field spec but not a valid Employee API field

**Location:** `task_types.py` line 67 (field spec), affects `executor.py` line 250
**Details:** The `TASK_FIELD_SPECS` for `CREATE_EMPLOYEE` lists `start_date` as an optional field. While the executor itself does not send `startDate` to the API (so no crash will occur), the classifier may extract `start_date` from user input and it will be silently ignored. This is the same class of bug as the `startDate` issue previously found -- the field spec implies support for something the API does not accept on Employee objects.
**Impact:** User-specified start dates on employees are silently dropped.
**Suggested fix:** Remove `start_date` from `TASK_FIELD_SPECS[CREATE_EMPLOYEE]["optional"]` since Employee has no `startDate` field. If employment start date tracking is needed, it would go through `/employee/employment` endpoint instead.

---

### 2. CRITICAL: `_exec_invoice_with_payment` -- VAT multiplier hardcoded to 1.25, ignores actual product VAT rates

**Location:** Lines 818-822
**Details:** When computing `paid_amount` from order lines, the code assumes 25% VAT for all lines (`total *= 1.25`). This is incorrect when:
- Products have 15% VAT (food) or 12% VAT (transport/hotel) or 0% VAT (exempt)
- Lines use mixed VAT rates
- Lines already specify `unitPriceIncludingVatCurrency` (the code checks `unitPriceExcludingVatCurrency` but the calculation still multiplies by 1.25 even for mixed-rate scenarios)

The `has_ex_vat` check on line 820 uses `any()`, so if even ONE line has ex-VAT pricing, ALL lines get the 1.25 multiplier applied to their total -- even lines that used `unitPriceIncludingVatCurrency`.

**Impact:** Incorrect payment amounts registered. Overpayment or underpayment on invoices with non-standard VAT rates.
**Suggested fix:** Calculate VAT per-line based on the actual VAT type of each product, or only multiply the ex-VAT portion by 1.25. Better yet, fetch the invoice total from the API response after creating the invoice rather than computing it client-side.

---

### 3. CRITICAL: `_exec_invoice_with_payment` -- Mixed price types in total calculation

**Location:** Lines 813-814
**Details:** The total calculation sums `unitPriceExcludingVatCurrency` OR `unitPriceIncludingVatCurrency` interchangeably:
```python
ol.get("unitPriceExcludingVatCurrency") or ol.get("unitPriceIncludingVatCurrency") or 0.0
```
Then on line 821, if ANY line has ex-VAT pricing, the entire total is multiplied by 1.25. This means lines with inc-VAT pricing get double-VAT applied.

**Example:** Line A: 100 ex-VAT, Line B: 125 inc-VAT. Total = 225. `has_ex_vat = True`. Final = 225 * 1.25 = 281.25. Correct would be 250.
**Impact:** Wrong payment amount when order lines mix ex-VAT and inc-VAT pricing.
**Suggested fix:** Separate the sums for ex-VAT and inc-VAT lines, apply multiplier only to the ex-VAT portion.

---

### 4. HIGH: `_exec_create_product` -- Uses `priceExcludingVatCurrency` instead of `priceExcludingVat`

**Location:** Lines 477-479
**Details:** The Tripletex Product API field for price is `priceExcludingVatCurrency` and `priceIncludingVatCurrency`. The standard documented field names are `priceExcludingVat` and `priceIncludingVat`. The Tripletex API may accept the `*Currency` variants as they relate to multi-currency support, but the canonical fields for NOK-only are `priceExcludingVat` and `priceIncludingVat`. If the sandbox only accepts the non-currency variants, product creation with prices will fail silently (price not set) or error.
**Impact:** Product prices may not be set correctly depending on API version.
**Suggested fix:** Verify against sandbox which field names work. Consider sending both variants or using the non-currency versions as primary.

---

### 5. HIGH: `_find_employee` -- Returns first employee when no search criteria match

**Location:** Line 133
**Details:** If `last_name` filtering finds no matches (both exact and fuzzy), the function falls through to `return employees[0]` -- returning a random employee. This is especially dangerous for `_exec_delete_employee` and `_exec_update_employee`, which could delete or modify the wrong employee.
**Impact:** Wrong employee updated/deleted when last name doesn't match any results.
**Suggested fix:** Return `None` when last_name is specified but no matches found, instead of falling through to `employees[0]`.

---

### 6. HIGH: `_find_employee` -- Email search is mutually exclusive with firstName search

**Location:** Lines 111-114
**Details:** The code uses `elif email` -- so if `first_name` is set, `email` is never used as a search parameter, even when both are available. This means a search with first_name="John" and email="john@test.com" will return ALL Johns, not filtering by email.
**Impact:** May find wrong employee when multiple employees share the same first name.
**Suggested fix:** Include both `firstName` and `email` in params when both are available.

---

### 7. HIGH: `_exec_register_payment` -- No amount validation, `None` amount sent to API

**Location:** Lines 727, 739
**Details:** If no amount field is found in `fields`, `amount` remains `None`. The `_clean` function will strip `paidAmount: None`, and the API call proceeds without `paidAmount`. The Tripletex API requires `paidAmount` for payment registration and will return a 400 error.
**Impact:** Unnecessary 4xx error (hurts efficiency score) instead of a clean early-return error message.
**Suggested fix:** Add an early check: `if not amount: return {"success": False, "error": "No payment amount specified"}`.

---

### 8. HIGH: `_exec_delete_travel_expense` -- Crashes when title match fails and expenses list is empty

**Location:** Lines 959-963
**Details:** If `title` is provided but no expense matches by title, `match` is `None`, and `expense_id = match["id"]` raises `TypeError: 'NoneType' object is not subscriptable`. Wait -- actually line 963 has a ternary: `expense_id = match["id"] if match else expenses[-1]["id"]`. This falls back to the last expense. So the bug is different: it deletes the WRONG expense (last one) when the title doesn't match.
**Impact:** Wrong travel expense deleted when title search fails.
**Suggested fix:** Return an error when the title is specified but not found, rather than deleting an unrelated expense.

---

### 9. HIGH: `_exec_create_customer` -- `isCustomer` field never set

**Location:** Lines 421-437
**Details:** When creating a customer via the Tripletex API, `isCustomer: true` should be explicitly set. Without it, the entity might be created as a generic contact/supplier depending on API defaults. The `isCustomer` flag listed in the problem description as a standard field is not included in the payload.
**Impact:** Created entities may not appear in customer-specific views/searches.
**Suggested fix:** Add `"isCustomer": True` to the customer creation payload (or at minimum as a default).

---

### 10. HIGH: `_exec_update_customer` -- Existing address lost when `postalAddress` is None

**Location:** Lines 448-460
**Details:** Unlike `_exec_update_employee` which preserves the existing address when no new address is provided (lines 326-329), `_exec_update_customer` uses `_build_address(fields, "new_") or _build_address(fields)`. If neither produces an address, `postalAddress` becomes `None`, which `_clean` strips. However, Tripletex PUT may interpret a missing `postalAddress` as "clear the address" depending on the API implementation.
**Impact:** Potential data loss -- existing customer address cleared on unrelated updates.
**Suggested fix:** Preserve existing address: `or cust.get("postalAddress")`.

---

### 11. MEDIUM: `_resolve_vat_type` -- Fallback IDs (3 and 6) are hardcoded magic numbers

**Location:** Lines 241-243
**Details:** The fallback `return 3` for 25% VAT and `return 6` for 0% VAT assumes specific IDs that may differ between Tripletex sandbox instances. If the sandbox uses different IDs, product creation will reference a non-existent or wrong VAT type.
**Impact:** Products created with wrong VAT type in sandboxes with different VAT type ID numbering.
**Suggested fix:** Remove hardcoded fallbacks and return `None` on lookup failure, then handle `None` in callers. Or log a clear warning when using fallback IDs.

---

### 12. MEDIUM: `_resolve_vat_type` -- `typeOfVat: "outgoing"` filter may return empty results

**Location:** Line 222
**Details:** The query parameter `typeOfVat` with value `"outgoing"` may not be supported by all Tripletex API versions. If it returns an empty list, the function falls through to the hardcoded fallback IDs. However, the second pass on lines 233-236 also iterates `vat_types` which is the same (potentially empty) list -- it cannot find anything the first pass didn't.
**Impact:** Falls to unreliable hardcoded fallbacks unnecessarily. Should try a broader search if filtered search returns empty.
**Suggested fix:** If `vat_types` is empty from the filtered query, retry with no filter: `await client.get_vat_types()`.

---

### 13. MEDIUM: `_exec_create_travel_expense` -- `date` field on travel expense payload may be invalid

**Location:** Line 909
**Details:** The payload includes a top-level `"date"` field set from `departure_date` or `date`. The Tripletex `/travelExpense` POST may not accept a top-level `date` field -- the date information belongs inside `travelDetails`. Sending an unknown field could cause a 400 error or be silently ignored.
**Impact:** Travel expense may be created without a date, or the API may reject the payload.
**Suggested fix:** Verify whether `/travelExpense` POST accepts top-level `date`. If not, remove it and rely on `travelDetails.departureDate`.

---

### 14. MEDIUM: `_exec_create_travel_expense` -- `travelDetails` sub-fields may use wrong API names

**Location:** Lines 893-903
**Details:** The field names used in `travel_details` (`departureDate`, `returnDate`, `departureFrom`, `destination`, `departureTime`, `returnTime`, `purpose`, `isForeignTravel`, `isDayTrip`) need verification against the actual Tripletex API schema. The Tripletex API may use different field names (e.g., `isForeignTrip` instead of `isForeignTravel`, or camelCase differences).
**Impact:** Travel details silently ignored or API error if field names are wrong.
**Suggested fix:** Verify field names against Tripletex API documentation or sandbox testing.

---

### 15. MEDIUM: `_exec_update_project` -- Extra API call: fetches project by ID after already searching by name

**Location:** Lines 1050-1059
**Details:** When `project_id` is not provided, the code searches by name (1 API call), extracts the ID, then does `client.get_project(int(project_id))` (2nd API call) to get the full project with version. The search result from `get_projects` already returns objects with `id` and `version`. Could use `projects[0]` directly and save an API call.
**Impact:** Wastes 1 API call per project update (hurts efficiency score).
**Suggested fix:** Use `proj = projects[0]` when found via search, only call `get_project()` when starting with a raw `project_id`.

---

### 16. MEDIUM: `_exec_project_billing` -- Same extra API call issue

**Location:** Lines 1097-1107
**Details:** Same pattern as `_exec_update_project` -- searches by name, then re-fetches by ID. The search already returns the customer reference.
**Impact:** Wastes 1 API call per project billing operation.
**Suggested fix:** Use the project object from the search results directly when `customer` ref is already included.

---

### 17. LOW: `_exec_delete_employee` -- Fallback `isContact: True` may not be a valid Employee field

**Location:** Line 384
**Details:** The fallback when DELETE returns 403 tries to set `isContact: True` on the employee. This field may not exist on the Employee object in Tripletex. If the API rejects it, the inner `except Exception: pass` silently swallows the error.
**Impact:** Fallback silently fails. The user gets a misleading "Marked as contact" response when nothing actually changed.
**Suggested fix:** Verify `isContact` is a valid Employee field. If not, use a different approach (e.g., move to a "disabled" department) or return an honest error.

---

### 18. LOW: `_exec_create_department` -- `departmentNumber` may need to be unique

**Location:** Lines 489-497, also line 161
**Details:** In `_ensure_department` (line 161), a default department is created with `departmentNumber: "1"`. If this is called multiple times (unlikely but possible), or if "1" already exists, the API may reject the creation. The `_exec_create_department` executor passes through whatever the classifier extracts, but if no number is provided, it's omitted -- which may cause the API to auto-assign or error depending on whether it's required.
**Impact:** Department creation may fail if number conflicts exist.
**Suggested fix:** Handle the duplicate department number case, or auto-increment.

---

### 19. LOW: `_exec_error_correction` -- `e.detail[:200]` crashes if `detail` is None

**Location:** Lines 1346, 1355, 1390, 1430
**Details:** The code accesses `e.detail[:200]` in multiple places. While `TripletexAPIError.__init__` sets `self.detail = detail` from `response.text[:500]`, if somehow `detail` is `None` (e.g., subclassing or direct construction), this would crash with `TypeError`. In practice this is unlikely given the current `TripletexAPIError` implementation.
**Impact:** Extremely unlikely crash in error logging paths.
**Suggested fix:** Use `(e.detail or "")[:200]` for defensive coding.

---

## Functions Audited (No Issues Found)

| Function | Lines | Notes |
|----------|-------|-------|
| `_today` | 50-51 | Clean |
| `_get` | 54-56 | Clean |
| `_ref` | 59-62 | Clean, handles None correctly |
| `_build_address` | 65-77 | Clean |
| `_clean` | 80-81 | Clean |
| `_find_customer` | 136-142 | Clean (simple search) |
| `_ensure_bank_account` | 165-195 | Clean, good fallback logic |
| `_build_order_lines` | 573-609 | Clean, handles both price types |
| `_create_invoice_from_order` | 612-640 | Clean |
| `_exec_create_invoice` | 643-675 | Clean, good customer creation fallback |
| `_exec_invoice_existing_customer` | 682-698 | Clean |
| `_exec_create_credit_note` | 745-775 | Clean |
| `_exec_set_employee_roles` | 393-416 | Clean (notes limitation in docstring) |
| `_exec_find_customer` | 1029-1042 | Clean |
| `_exec_delete_project` | 1074-1089 | Clean |
| `_exec_project_with_customer` | 1005-1026 | Clean |
| `_exec_bank_reconciliation` | 1120-1279 | Clean (extensive fallback logic) |
| `_exec_year_end_closing` | 1442-1642 | Clean (multi-approach, good fallbacks) |
| `_exec_enable_module` | 1645-1761 | Clean |
| `execute_task` | 1812-1840 | Clean (top-level error handling catches both API and unexpected errors) |

---

## Recommendations (Priority Order)

1. **Fix the VAT multiplier logic** (Issues 2, 3) -- This will cause incorrect payment amounts. Fetch the actual invoice total from the API instead of computing it.
2. **Fix `_find_employee` fallthrough** (Issue 5) -- Prevent accidental updates/deletions of wrong employees.
3. **Fix `_exec_delete_travel_expense` wrong-deletion fallback** (Issue 8) -- Same class of "wrong entity affected" bug.
4. **Add `isCustomer: true` to customer creation** (Issue 9).
5. **Fix email search exclusion in `_find_employee`** (Issue 6).
6. **Add payment amount validation** (Issue 7).
7. **Verify product price field names** against sandbox (Issue 4).
8. **Fix VAT type fallback** to retry without filter (Issues 11, 12).
9. **Eliminate redundant API calls** in update_project and project_billing (Issues 15, 16).
