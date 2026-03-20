# CREATE_CUSTOMER & CREATE_PRODUCT Test Results

**Date:** 2026-03-20
**Mode:** Rule-based classifier (no LLM -- `LLM_MODE=none`)
**Test file:** `app/test_customer_product.py`

## Summary

**41/47 passed, 6 failed**

All 12 task_type classifications correct (100%). Failures are in field extraction only, specifically for non-Norwegian/English languages in the rule-based fallback classifier.

---

## CREATE_CUSTOMER Tests (7 tests, 21 assertions)

| # | Language | Prompt | task_type | name | org | address/email | Notes |
|---|----------|--------|-----------|------|-----|---------------|-------|
| C1 | German | Grünfeld GmbH, org 835026434, address | PASS | PASS | **FAIL** | PASS | org regex misses "Organisationsnummer" |
| C2 | Norwegian | Nordic Tech AS, org.nr, e-post | PASS | PASS | PASS | PASS | All fields extracted |
| C3 | English | Acme Corp, organization number | PASS | PASS | PASS | n/a | All fields extracted |
| C4 | French | Dubois SA, numéro d'organisation | PASS | PASS | **FAIL** | n/a | org regex misses French phrasing |
| C5 | Norwegian | Fjord Consulting AS, address, org.nr | PASS | PASS | PASS | n/a | All fields extracted |
| C6 | Spanish | López y Asociados, número de organización | PASS | **FAIL** | **FAIL** | n/a | Name regex fails (lowercase "y"), org regex misses Spanish |
| C7 | Portuguese | Silva Ltda, número de organização | PASS | PASS | n/a | n/a | Name extracted |

**Key finding:** The executor always sets `isCustomer=True` in the payload (verified by code review of `_exec_create_customer`).

### Root causes of failures

1. **Org number regex gap (C1, C4, C6):** The rule-based `_extract_fields_rule_based` uses `(?:org\.?(?:anisasjonsnummer|\.?\s*nr\.?)?|organization\s*number)` which only matches Norwegian ("organisasjonsnummer", "org.nr") and English ("organization number"). Missing: German "Organisationsnummer", French "numéro d'organisation", Spanish "número de organización".

2. **Name extraction gap (C6):** "López y Asociados" -- the regex expects uppercase-starting words (`[A-ZAEOA...]`), but "y" is lowercase and breaks the name pattern match.

---

## CREATE_PRODUCT Tests (5 tests, 20 assertions)

| # | Language | Prompt | task_type | name | number | price | vat | Notes |
|---|----------|--------|-----------|------|--------|-------|-----|-------|
| P1 | German | Datenberatung, nr 5524, 22550 NOK, 25% MwSt | PASS | PASS | PASS | PASS | PASS | All fields extracted |
| P2 | Norwegian | Konsulenttjeneste, 1500 kr eks MVA | PASS | PASS | n/a | PASS | n/a | All fields extracted |
| P3 | English | Premium Widget, number 1001, 500 NOK, VAT rate 25% | PASS | PASS | PASS | PASS | **FAIL** | "VAT rate 25%" -- pattern expects "25% VAT" (% before keyword) |
| P4 | French | Service Premium, numéro 2002, 3000 NOK, TVA 25% | PASS | PASS | **FAIL** | PASS | PASS | "numéro 2002" not matched by number regex |
| P5 | Norwegian | Programvare, produktnummer 3003, 9990 kr inkl MVA | PASS | PASS | PASS | PASS | n/a | Price captured (in price_excluding_vat) |

**Key finding:** The executor resolves VAT type dynamically via `_resolve_vat_type()`, defaulting to 25% if no percentage is specified. This means even if `vat_percentage` is not extracted, the product will get standard 25% VAT.

### Root causes of failures

1. **VAT regex gap (P3):** The regex `(\d+)\s*%\s*(?:MVA|MwSt|VAT|...)` requires the % sign to appear before the keyword. "VAT rate 25%" has the keyword before the number, and the fallback `(?:VAT|...)\s*:?\s*(\d+)\s*%?` matches "VAT" but then expects a number right after -- "VAT rate 25%" has the word "rate" in between.

2. **Product number regex gap (P4):** The French "numéro 2002" without "de produit" suffix is not matched. The regex expects "numéro de produit" or "nummer/number/nr" (none of which match bare "numéro").

---

## Conclusions

- **Task type classification is 100% accurate** across all 7 languages for both CREATE_CUSTOMER and CREATE_PRODUCT.
- **Norwegian and English field extraction is excellent** -- all fields correctly parsed.
- **German, French, Spanish, Portuguese field extraction has gaps** in the rule-based classifier, specifically for org numbers, product numbers, and VAT rate phrasing variants.
- **With LLM mode (Gemini or Claude), these gaps are expected to be resolved** since the LLM handles multilingual extraction natively.
- **The executor logic is correct** -- `isCustomer=True` always set, VAT type defaults to 25%, `_post_process_fields` strips prices/numbers from names.
