# TEST-EMPLOYEE: CREATE_EMPLOYEE Classification + Payload Tests

**Classifier mode:** `none`
**Total: 7 tests | PASS: 3 | FAIL: 4**

## Test 1 [FAIL]
**Prompt:** `Vi har en ny ansatt som heter Astrid Strand, født 4. May 1986. Opprett vedkommen...`

| Check | Status | Value |
|-------|--------|-------|
| task_type | PASS | create_employee |
| first_name | PASS | Astrid |
| last_name | PASS | Strand |
| email | PASS | astrid.strand@example.com |
| date_of_birth | FAIL | got='', expected='1986-05-04' |
| no_startDate | PASS | not present |

**All extracted fields:** `{"name": "Astrid Strand", "first_name": "Astrid", "last_name": "Strand", "email": "astrid.strand@example.com"}`

## Test 2 [PASS]
**Prompt:** `Opprett en ansatt med navn Ola Nordmann, ola@example.org. Han skal være kontoadm...`

| Check | Status | Value |
|-------|--------|-------|
| task_type | PASS | create_employee |
| first_name | PASS | Ola |
| last_name | PASS | Nordmann |
| email | PASS | ola@example.org |
| user_type->mapped | PASS | ADMINISTRATOR -> EXTENDED |
| no_startDate | PASS | not present |

**All extracted fields:** `{"name": "Ola Nordmann", "first_name": "Ola", "last_name": "Nordmann", "email": "ola@example.org", "user_type": "ADMINISTRATOR"}`

## Test 3 [FAIL]
**Prompt:** `Create employee John Smith, john@smith.com, administrator role`

| Check | Status | Value |
|-------|--------|-------|
| task_type | FAIL | got=set_employee_roles, expected=create_employee |
| first_name | PASS | John |
| last_name | PASS | Smith |
| email | PASS | john@smith.com |
| user_type->mapped | PASS | ADMINISTRATOR -> EXTENDED |
| no_startDate | PASS | not present |

**All extracted fields:** `{"email": "john@smith.com", "user_type": "ADMINISTRATOR", "first_name": "John", "last_name": "Smith"}`

## Test 4 [FAIL]
**Prompt:** `Erstellen Sie einen Mitarbeiter Anna Müller, anna@mueller.de. Sie soll Kontoadmi...`

| Check | Status | Value |
|-------|--------|-------|
| task_type | PASS | create_employee |
| first_name | FAIL | got='', expected='Anna' |
| last_name | FAIL | got='', expected='Müller' |
| user_type->mapped | PASS | ADMINISTRATOR -> EXTENDED |
| no_startDate | PASS | not present |

**All extracted fields:** `{"email": "anna@mueller.de", "user_type": "ADMINISTRATOR"}`

## Test 5 [PASS]
**Prompt:** `Créer un employé Pierre Dupont, pierre@dupont.fr, rôle administrateur`

| Check | Status | Value |
|-------|--------|-------|
| task_type | PASS | create_employee |
| first_name | PASS | Pierre |
| last_name | PASS | Dupont |
| user_type->mapped | PASS | ADMINISTRATOR -> EXTENDED |
| no_startDate | PASS | not present |

**All extracted fields:** `{"first_name": "Pierre", "last_name": "Dupont", "email": "pierre@dupont.fr", "user_type": "ADMINISTRATOR"}`

## Test 6 [PASS]
**Prompt:** `Opprett ansatt Kari Berge med e-post kari@berge.no. Ho skal ha adresse Storgata ...`

| Check | Status | Value |
|-------|--------|-------|
| task_type | PASS | create_employee |
| first_name | PASS | Kari |
| last_name | PASS | Berge |
| email | PASS | kari@berge.no |
| no_startDate | PASS | not present |
| extra:address_line1 | PASS | Storgata 5 |
| extra:postal_code | PASS | 0150 |
| extra:city | PASS | Oslo |

**All extracted fields:** `{"first_name": "Kari", "last_name": "Berge", "email": "kari@berge.no", "address_line1": "Storgata 5", "postal_code": "0150", "city": "Oslo"}`

## Test 7 [FAIL]
**Prompt:** `Ny ansatt: Erik Hansen, erik@hansen.no, avdeling Utvikling, telefon 99887766`

| Check | Status | Value |
|-------|--------|-------|
| task_type | PASS | create_employee |
| first_name | FAIL | got='', expected='Erik' |
| last_name | FAIL | got='', expected='Hansen' |
| email | PASS | erik@hansen.no |
| no_startDate | PASS | not present |
| extra:phone | PASS | 99887766 |

**All extracted fields:** `{"email": "erik@hansen.no", "phone": "99887766"}`

## Failure Analysis

### Test 1
- **date_of_birth**: got='', expected='1986-05-04'
- **Root cause**: Rule-based classifier date parser does not recognize English month name 'May' in Norwegian text. The `_RE_DATE_TEXT_NB` regex only matches Norwegian month names (januar-desember), and 'May' is not 'mai'.

### Test 3
- **task_type**: got=set_employee_roles, expected=create_employee
- **Root cause**: Rule-based regex `_KEYWORD_MAP` checks SET_EMPLOYEE_ROLES before CREATE_EMPLOYEE. The pattern `role.*employee` or `employee.*role` in 'administrator role' matches SET_EMPLOYEE_ROLES first.

### Test 4
- **first_name**: got='', expected='Anna'
- **last_name**: got='', expected='Müller'
- **Root cause**: German name pattern 'einen Mitarbeiter Anna Muller' does not match the rule-based name extraction regex which expects 'Mitarbeiter' directly followed by a capitalized name. The word 'einen' is not captured by the name-intro patterns in `_extract_fields_rule_based`.

### Test 7
- **first_name**: got='', expected='Erik'
- **last_name**: got='', expected='Hansen'
- **Root cause**: 'Ny ansatt: Erik Hansen' uses colon syntax. The rule-based name extractor looks for 'ansatt X Y' but the colon breaks the pattern match.

**Note:** These failures are specific to the rule-based classifier (no LLM). With Gemini or Claude LLM mode enabled, all 7 tests are expected to pass as the LLM handles multilingual name extraction, date parsing, and task disambiguation correctly.

## User Type Mapping Verification

The executor's `_USER_TYPE_MAP` in `_exec_create_employee` maps:
| Input | Maps To |
|-------|---------|
| ADMINISTRATOR | EXTENDED |
| ADMIN | EXTENDED |
| KONTOADMINISTRATOR | EXTENDED |
| RESTRICTED | NO_ACCESS |
| BEGRENSET | NO_ACCESS |
| INGEN_TILGANG | NO_ACCESS |
| NONE | NO_ACCESS |

Admin prompts (tests 2-5) that extract `user_type=ADMINISTRATOR` correctly map to `EXTENDED` in the executor.

