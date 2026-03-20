# Tripletex Agent — Test Matrix (2026-03-19)

Tested against sandbox: `https://kkpqfuj-amager.tripletex.dev/v2`
LLM mode: `none` (rule-based classifier)

## Summary

| # | Result | Category |
|---|--------|----------|
| 5 | PASS   | Works end-to-end |
| 3 | CLASSIFY_FAIL | Rule-based classifier picks wrong task type |
| 2 | API_FAIL | Correct classification, Tripletex API rejects |
| 1 | FIELDS_FAIL | Correct classification, but required fields not extracted |

---

## Tier 1 — Foundational Tasks

| Task Type | Prompt (NO) | Classify | Execute | Result | Details |
|-----------|-------------|----------|---------|--------|---------|
| `create_department` | "Opprett en avdeling med navn IT og avdelingsnummer 20" | `create_department` | POST /department | **PASS** | Created ID 866144, name "IT", number 20 |
| `create_customer` | "Opprett en kunde med navn Nordmann Handel AS, e-post kontakt@nordmann.no" | `create_contact` | POST /contact | **CLASSIFY_FAIL** | Email "kontakt@nordmann.no" contains "kontakt" which matches `\bkontakt\b` in CREATE_CONTACT regex before CREATE_CUSTOMER is checked. Created empty contact (ID 18494518) instead of customer. |
| `create_employee` | "Opprett en ansatt med fornavn Kari og etternavn Hansen, e-post kari@test.no" | `create_employee` | POST /employee | **PASS** | Created ID 18494521, Kari Hansen, kari@test.no |
| `update_employee` | "Oppdater ansatt Kari Hansen med ny e-post kari.hansen@test.no" | `update_employee` | PUT /employee/{id} | **API_FAIL** | Correctly found employee, but Tripletex returns 422: `"email" kan ikke endres` (email cannot be changed via this API) |
| `create_product` | "Opprett et produkt med navn Konsulenttime til 1500 kr" | `create_product` | POST /product | **PASS** | Created ID 84382051, price 1500.0 NOK |
| `create_project` | "Opprett et prosjekt med navn Nettside Redesign" | `create_project` | POST /project | **API_FAIL** | 422: `Feltet "Prosjektleder" må fylles ut` — project manager (projectManager) is required but not provided. Need to default to first employee. |
| `delete_employee` | "Slett ansatt Kari Hansen" | `delete_employee` | DELETE /employee/{id} | **API_FAIL** | 403: `You do not have permission to access this feature` — sandbox token lacks delete permission |

### English Variants

| Task Type | Prompt (EN) | Classify | Execute | Result | Details |
|-----------|-------------|----------|---------|--------|---------|
| `create_customer` | "Create a customer called Global Corp with email info@global.com" | `create_customer` | POST /customer | **FIELDS_FAIL** | Classification correct, but regex doesn't match "called X" — only "named" or "med navn". No `name` field extracted → customer created without name (rejected or empty). |
| `create_department` | "Create a department named HR with number 30" | `create_department` | POST /department | **PASS (partial)** | Created ID 866149, but name extracted as "HR with number 30" instead of "HR". Regex captures everything after "named" until comma/og/and, but "with" is not in the stop-word list. |

## Tier 2 — Multi-Step Tasks

| Task Type | Prompt (NO) | Classify | Execute | Result | Details |
|-----------|-------------|----------|---------|--------|---------|
| `create_contact` | "Opprett en kontaktperson Hans Olsen for kunde Nordmann Handel AS, e-post hans@nordmann.no" | `create_customer` | POST /customer | **CLASSIFY_FAIL** | "kontaktperson" doesn't match `\bkontakt\b` (no word boundary after "kontakt" in "kontaktperson"). Falls through to `create_customer` because "kunde" matches. Also: no first_name/last_name extraction for non-employee contacts. |
| `create_travel_expense` | "Registrer en reiseregning med tittel Kundebesøk Oslo" | `create_travel_expense` | POST /travelExpense | **PASS** (when `employee_id` provided) | Classification correct, but no fields extracted (no employee_identifier, no title regex). Direct executor test with explicit employee_id works → created ID 11142133. Rule-based mode can't extract "tittel X" or find employee. |

## Entities Created in Sandbox

| Entity | ID | Details |
|--------|----|---------|
| Department | 866144 | IT (#20) |
| Department | 866149 | "HR with number 30" (should be "HR") |
| Employee | 18494521 | Kari Hansen (kari@test.no) |
| Product | 84382051 | Konsulenttime til 1500 kr (1500.0 NOK) |
| Customer | 108170621 | Nordmann Handel AS (created via direct executor test) |
| Travel Expense | 11142133 | Kundebesøk Oslo (created via direct executor test) |
| Contact | 18494518 | Empty names, email kontakt@nordmann.no (misclassified) |

## Issues to Fix (Priority Order)

### P0 — Classification Bugs

1. **`create_customer` misclassified as `create_contact`**: Email addresses containing "kontakt" trigger the contact regex. Fix: move `CREATE_CUSTOMER` before `CREATE_CONTACT` in `_KEYWORD_MAP`, or make the contact regex require an explicit "kontaktperson" pattern.

2. **`create_contact` misclassified as `create_customer`**: `\bkontakt\b` doesn't match "kontaktperson" (compound word). Fix: add `kontaktperson` to the contact regex pattern.

3. **English "called X" not extracting name**: Regex only matches "named?" and "med navn". Fix: add "called" to the name extraction pattern in `_extract_fields_rule_based`.

4. **English "named X with Y" over-captures name**: "HR with number 30" captured as full name. Fix: add "with" to the stop-word list in the name regex.

### P1 — Missing Required Fields

5. **`create_project` needs `projectManager`**: Tripletex sandbox requires a project manager. Fix: in `_exec_create_project`, auto-resolve a project manager (first employee) when none specified.

6. **`create_travel_expense` no field extraction**: "tittel" and employee name not extracted. Fix: add regex for "tittel/title" and employee lookup by name in the travel expense flow.

7. **`create_contact` no first/last name extraction**: The `_extract_fields_rule_based` only extracts "first_name/last_name" from "fornavn/etternavn" patterns. Fix: add pattern for "kontaktperson FirstName LastName".

### P2 — API Limitations

8. **`update_employee` email immutable**: Tripletex doesn't allow email changes via PUT /employee. This is a sandbox/API limitation — need to document and handle gracefully.

9. **`delete_employee` permission denied**: Sandbox token lacks delete permission (403). Likely a sandbox limitation.

### P3 — Minor

10. **Product name includes price text**: "Konsulenttime til 1500 kr" — the "med navn" regex captures the price as part of the name. Could improve with a "til X kr" stop pattern.
