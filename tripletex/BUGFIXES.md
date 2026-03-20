# Tripletex Agent Bugfixes — 2026-03-20

## Bug 1: "fornavn/etternavn" pattern not recognized in classifier.py
**File:** `app/classifier.py` — `_extract_fields_generic()`
**Symptom:** "Opprett en ansatt med fornavn Ola og etternavn Nordmann" → `first_name='fornavn'`, `last_name='Ola'`
**Cause:** The keyword classifier's name extraction patterns didn't handle the Norwegian "fornavn X og etternavn Y" pattern. It matched "med" + next capitalized words instead.
**Fix:** Added explicit regex for `fornavn\s+(\S+)\s+(?:og\s+)?etternavn\s+(\S+)` before the generic name extraction fallback. Also changed the subsequent check from `if not first_name` (which was an UnboundLocalError) to `if not fields.get("first_name")`.

## Bug 2: Department number not extracted in classifier.py
**File:** `app/classifier.py` — `_extract_fields_generic()`
**Symptom:** "Opprett avdeling Markedsføring med avdelingsnummer 40" → `fields={'name': 'Markedsføring'}` (missing `department_number`)
**Cause:** The `CREATE_DEPARTMENT` branch in `_extract_fields_generic` only extracted the name, never the department number.
**Fix:** Added department number extraction regex matching "avdelingsnummer", "department number", "numéro", "nummer", etc.

## Bug 3: Invoice lines missing description in classifier.py
**File:** `app/classifier.py` — `_extract_fields_generic()`
**Symptom:** "3 stk Frakttjeneste til 2500 kr" → `lines=[{'unit_price': 2500.0, 'quantity': 3.0}]` (no `description`)
**Cause:** The invoice line builder only extracted unit_price and quantity from simple regex, never parsed the product name.
**Fix:** Added `_extract_invoice_lines()` function (ported from main.py) that extracts "N stk X til Y kr" patterns with description, quantity, and unit_price. Used as primary extractor before falling back to simple qty+price extraction.

## Bug 4: French department name included number text
**File:** `app/classifier.py` — `_post_process_fields()`
**Symptom:** "Créer département Finance numéro 90" → `name='Finance numéro 90'`
**Cause:** The `_post_process_fields` regex for stripping number text from department names only matched prefixed forms like "with number", "med nummer" etc. — not bare "numéro N".
**Fix:** Extended the regex to also match standalone `numéro|número|nummer|number|nr\.?` followed by digits.

## Bug 5: Org number falsely matched as phone in classifier.py
**File:** `app/classifier.py` — `_extract_fields_generic()`
**Symptom:** "Opprett kunde Fjord AS med org.nr 987654321" → `fields` included both `organization_number` and `phone` with value `987654321`
**Cause:** The phone regex `_RE_PHONE` is broad enough to match 9-digit org numbers.
**Fix:** Added a check before setting phone: if the text immediately before the match ends with an org-number keyword pattern (`org\.?\s*(?:nr\.?|nummer)?\s*:?\s*$`), skip the phone assignment.

## Bug 6: Customer name trailing colon in main.py
**File:** `app/main.py` — `_extract_fields_rule_based()`
**Symptom:** "Lag faktura til kunde Hansen AS: 3 stk..." → `customer_name='Hansen AS:'`
**Cause:** The customer name regex for invoice tasks didn't include `:` as a stop character, and `.rstrip(".,")` didn't strip colons.
**Fix:** Added `:\s*` as a stop pattern in the regex and changed rstrip to `rstrip(".,:")`.

## Bug 7: Org number matched as department_number in main.py
**File:** `app/main.py` — `_extract_fields_rule_based()`
**Symptom:** "Opprett kunde Fjord AS med org.nr 987654321" → `department_number='987654321'`
**Cause:** The department number regex included `nr\.?\s*` which matched "nr" in "org.nr", extracting the org number as a department number for all task types.
**Fix:** Restricted department number extraction to only run when `task_type == TaskType.CREATE_DEPARTMENT`.
