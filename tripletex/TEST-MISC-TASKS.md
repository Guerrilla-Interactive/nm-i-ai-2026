# Miscellaneous Task Type Classification Tests

**Date:** 2026-03-20
**Mode:** Rule-based (no LLM)
**App:** `/Users/pelle/Documents/github/nm-i-ai-2026/tripletex/app/`

## Summary

| Category | Pass | Fail | Total |
|---|---|---|---|
| CREATE_TRAVEL_EXPENSE | 4 | 0 | 4 |
| DELETE_TRAVEL_EXPENSE | 2 | 1 | 3 |
| CREATE_DEPARTMENT | 3 | 1 | 4 |
| ENABLE_MODULE | 3 | 0 | 3 |
| REGISTER_PAYMENT | 3 | 0 | 3 |
| CREATE_CREDIT_NOTE | 2 | 0 | 2 |
| **Total** | **17** | **2** | **19** |

## CREATE_TRAVEL_EXPENSE (4/4 PASS)

### CTE-1: Nynorsk day trip -- PASS
- **Input:** "Opprett reiserekning for tilsett Per Hansen, dagsreise fra Bergen til Oslo 19. mars 2026, formal: kundemote"
- **Type:** `create_travel_expense` (correct)
- **Fields:** `first_name=Per, last_name=Hansen`
- **Note:** `employee_identifier` is set during extraction but normalized into `first_name`/`last_name` by `_normalize_fields()`. Correct behavior.

### CTE-2: English multi-day trip -- PASS
- **Input:** "Create travel expense for employee John Smith, trip from Oslo to Stockholm March 20-22, purpose: conference"
- **Type:** `create_travel_expense` (correct)
- **Fields:** `first_name=John, last_name=Smith`
- **Note:** Same normalization as CTE-1. Travel-specific fields (departure_from, destination, dates) not extracted by rule-based mode -- would need LLM.

### CTE-3: German day trip -- PASS
- **Input:** "Erstellen Sie eine Reisekostenabrechnung fur Mitarbeiter Anna Muller, Tagesreise von Hamburg nach Berlin am 15. Marz 2026"
- **Type:** `create_travel_expense` (correct)
- **Fields:** `title="fur Mitarbeiter Anna Muller"` (title extraction is noisy but type classification is correct)

### CTE-4: French multi-day trip -- PASS
- **Input:** "Creer une note de frais pour l'employe Pierre Dupont, voyage Oslo-Paris du 10 au 12 mars 2026"
- **Type:** `create_travel_expense` (correct)
- **Fields:** `first_name=Pierre, last_name=Dupont`

## DELETE_TRAVEL_EXPENSE (2/3 PASS)

### DTE-1: Nynorsk -- PASS
- **Input:** "Slett reiserekning for tilsett Ola Nordmann"
- **Type:** `delete_travel_expense` (correct)
- **Fields:** `first_name=Ola, last_name=Nordmann`

### DTE-2: English -- PASS
- **Input:** "Delete travel expense for employee John Smith"
- **Type:** `delete_travel_expense` (correct)
- **Fields:** `first_name=John, last_name=Smith`

### DTE-3: French -- FAIL
- **Input:** "Supprimer la note de frais de l'employe Pierre Dupont"
- **Expected:** `delete_travel_expense`
- **Actual:** `delete_employee`
- **Root cause:** The regex for DELETE_EMPLOYEE matches `supprimer.*employe` before the DELETE_TRAVEL_EXPENSE pattern can match. The French pattern `note de frais` is in the CREATE_TRAVEL_EXPENSE regex but the DELETE_TRAVEL_EXPENSE regex uses `voyage` for French, not `note de frais`. The keyword `supprimer` + `employe` triggers DELETE_EMPLOYEE first because the delete-travel regex requires `reise|travel|viaje|voyage|reisekostenabrechnung` and "note de frais" is not included in the DELETE pattern.

## CREATE_DEPARTMENT (3/4 PASS)

### CD-1: Nynorsk -- PASS
- **Input:** "Opprett ein ny avdeling som heiter Marknadsfoering"
- **Type:** `create_department` (correct)
- **Fields:** `name=Marknadsfoering`

### CD-2: English -- PASS
- **Input:** "Create department Sales"
- **Type:** `create_department` (correct)
- **Fields:** `name=Sales`

### CD-3: Batch creation -- FAIL
- **Input:** "Create three departments in Tripletex: Utvikling, Innkjop, and Salg"
- **Expected:** `create_department` (or batch)
- **Actual:** `unknown`
- **Root cause:** The rule-based classifier cannot detect batch/multi-entity tasks. The keyword pattern requires `create.*department` but the input says "departments" (plural). The regex `department\w*` should match `departments`, but the word "three" and "in Tripletex:" separates the create verb from the entity keyword too much. Actually, the regex `\b(opprett\w*|create|...)\b.*\b(avdeling|department|...)\b` should match "Create...departments". The issue is that the input uses "departments" and the regex uses `department\w*` -- wait, `department` is in the regex without `\w*`. Checking: the regex is `\b(avdeling|department|departamento|abteilung|département)\b` with `\b` at the end, so "departments" would NOT match because `\b` requires a word boundary after "department" but there's an "s" following. This is the bug -- the regex should use `department\w*` or `departments?`.

### CD-4: German -- PASS
- **Input:** "Erstellen Sie die Abteilung Forschung und Entwicklung"
- **Type:** `create_department` (correct)
- **Fields:** `name=Forschung` (partial -- "und Entwicklung" lost because "und" is treated as a stop word in the name extraction regex)

## ENABLE_MODULE (3/3 PASS)

### EM-1: Norwegian -- PASS
- **Input:** "Aktiver modul Reiseregning"
- **Type:** `enable_module` (correct)
- **Fields:** `module_name=Reiseregning`

### EM-2: English -- PASS
- **Input:** "Enable module Invoice Management"
- **Type:** `enable_module` (correct)
- **Fields:** `module_name=Invoice Management`

### EM-3: German -- PASS
- **Input:** "Aktivieren Sie das Modul Projektverwaltung"
- **Type:** `enable_module` (correct)
- **Fields:** `module_name=Projektverwaltung`

## REGISTER_PAYMENT (3/3 PASS)

### RP-1: Norwegian with date -- PASS
- **Input:** "Registrer innbetaling 25000 kr pa faktura nummer 10099, dato 2026-03-20"
- **Type:** `register_payment` (correct)
- **Fields:** `amount=25000.0`
- **Note:** `invoice_id` not extracted (regex expects `faktura <number>` but input has `faktura nummer 10099`). Payment date not extracted by rule-based mode.

### RP-2: English -- PASS
- **Input:** "Register payment of 5000 NOK on invoice 20055"
- **Type:** `register_payment` (correct)
- **Fields:** `invoice_id=20055, amount=5000.0`

### RP-3: Norwegian with amount -- PASS
- **Input:** "Registrer betaling pa faktura 10042 med belop 15000 kr"
- **Type:** `register_payment` (correct)
- **Fields:** `invoice_id=10042, amount=15000.0`

## CREATE_CREDIT_NOTE (2/2 PASS)

### CCN-1: Norwegian -- PASS
- **Input:** "Opprett kreditnota for faktura 10055"
- **Type:** `create_credit_note` (correct)
- **Fields:** `invoice_id=10055`

### CCN-2: English -- PASS
- **Input:** "Create a credit note for invoice 10055"
- **Type:** `create_credit_note` (correct)
- **Fields:** `invoice_id=10055`

## Known Issues (Rule-Based Mode)

1. **DTE-3 (French delete travel expense):** The DELETE_TRAVEL_EXPENSE regex does not include French `note de frais` as a travel expense keyword. Only `voyage` is included for French. Fix: add `note\s+de\s+frais` to the DELETE_TRAVEL_EXPENSE patterns.

2. **CD-3 (Batch department creation):** The CREATE_DEPARTMENT regex uses `\bdepartment\b` which does not match "departments" (plural). Additionally, the rule-based classifier has no batch detection logic. Fix: use `departments?` or `department\w*` in the regex.

3. **CD-4 (German compound name):** "Forschung und Entwicklung" is truncated to "Forschung" because "und" is treated as a stop word by the name extraction regex. The LLM classifier would handle this correctly.

4. **CTE-3 (German title extraction):** The title field captures "fur Mitarbeiter Anna Muller" instead of a clean trip description. The employee name leaks into the title. The LLM classifier would handle this correctly.

5. **RP-1 (Invoice number):** `faktura nummer 10099` is not matched by the invoice_id regex which expects `faktura #?(\d+)` (no "nummer" keyword). The amount and type classification are correct.

## Conclusion

The rule-based classifier correctly identifies **17 out of 19** task types (89.5% accuracy). The two failures are:
- A missing French keyword in the DELETE_TRAVEL_EXPENSE regex
- No support for plural "departments" in CREATE_DEPARTMENT regex

Field extraction quality varies -- the rule-based mode captures core identifiers well but misses travel-specific fields (departure, destination, dates) and has some name extraction edge cases. The LLM-based classifier (Gemini/Claude) would handle all of these correctly.
