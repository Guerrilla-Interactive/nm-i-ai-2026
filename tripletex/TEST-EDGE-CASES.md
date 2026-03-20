# Edge Case Test Results

> Endpoint: `https://tripletex-agent-785696234845.europe-north1.run.app`
> LLM mode: `none` (rule-based classifier)
> Tested: 2026-03-20

## Test Results

| # | Prompt | Classification | Fields Correct | Notes |
|---|--------|---------------|----------------|-------|
| Edge 1 | `Opprett avdeling ECMarketing` (no number) | `create_department` ✅ | name ✅ | Dept created without number |
| Edge 2 | `Lag faktura til TestFirma AS: 10 stk ECWidget til 250 kr, 5 stk ECService til 500 kr` | `create_invoice` ✅ | customer_name ❌→✅ (FIXED), lines ✅ | **BUG FIXED:** customer_name not extracted without `kunde` keyword |
| Edge 3 | `Crear cliente ECMadrid SL con email madrid@test.es` | `create_customer` ✅ | name ✅ email ✅ | Spanish works |
| Edge 4 | `Opprett ansatt med fornavn ECAnna og etternavn ECBerg, e-post ecanna@test.no, født 1990-05-15` | `create_employee` ✅ | first/last ✅ email ✅ dob ❌→✅ (FIXED) | **BUG FIXED:** `date_of_birth` not extracted |
| Edge 5 | `Opprett produkt ECDeluxeWidget til 1500 kr` | `create_product` ✅ | name ✅ price ✅ | Works correctly |
| Edge 6 | `Criar empregado ECMaria ECSilva` | `unknown` ❌→✅ (FIXED) | — | **BUG FIXED:** Portuguese `empregado` not in `_KEYWORD_MAP` |
| Edge 7 | `Opprett reiseregning for ansatt ECAnna ECLarsen` | `create_employee` ❌→✅ (FIXED) | employee_identifier ✅ | **BUG FIXED:** `ansatt` matched employee before travel expense |
| Edge 8 | `Slett ansatt ECGhost ECPerson` | `delete_employee` ✅ | first/last ✅ | Classification correct (target may not exist) |

## Bugs Found and Fixed

### Bug 1: Travel expense misclassified as employee (FIXED)
- **Problem:** `_KEYWORD_MAP` had `CREATE_EMPLOYEE` before `CREATE_TRAVEL_EXPENSE`. Prompt "Opprett reiseregning **for ansatt** ECAnna ECLarsen" matched the `ansatt` keyword in the employee pattern first.
- **Fix:** Moved all travel expense entries before employee entries in `_KEYWORD_MAP`. Also put `\breiseregning\b` first in the travel expense patterns (keyword-only match, no verb needed).
- **Side fix:** Travel expense title extraction was catching "for ansatt X Y" as the title when no actual title was present. Added guard to skip employee-reference-only strings.

### Bug 2: Portuguese `empregado` not recognized (FIXED)
- **Problem:** `_KEYWORD_MAP` employee patterns didn't include Portuguese `empregado`.
- **Fix:** Added `empregado` to CREATE_EMPLOYEE, DELETE_EMPLOYEE, and UPDATE_EMPLOYEE patterns.

### Bug 3: `date_of_birth` not extracted (FIXED)
- **Problem:** `_extract_fields_rule_based` had no pattern for "født YYYY-MM-DD" or similar date-of-birth patterns.
- **Fix:** Added extraction for `født/born/date_of_birth/fødselsdato/geburtsdatum/fecha_de_nacimiento/date_de_naissance` followed by `YYYY-MM-DD`.

### Bug 4: Invoice customer_name without `kunde`/`customer` keyword (FIXED)
- **Problem:** "Lag faktura til TestFirma AS:" — the customer_name regex required `kunde/customer/client` keyword. Direct "faktura til X:" pattern wasn't matched.
- **Fix:** Added fallback regex: `faktura til/for/to X:` captures customer name after the preposition when no entity keyword is present.

## Summary

**8 edge cases tested. 4 bugs found and fixed in `main.py`.**

All fixes are in the rule-based classifier (`_KEYWORD_MAP` ordering + `_extract_fields_rule_based` patterns). No changes to the LLM-based classifiers (Claude/Gemini).

Note: These fixes are local only — Cloud Run still has the old code. Redeploy needed to apply fixes.
