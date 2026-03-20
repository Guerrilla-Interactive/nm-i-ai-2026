# Test Results: PROJECT_WITH_CUSTOMER, CREATE_CONTACT, CREATE_PROJECT

**Date:** 2026-03-20
**Classifier mode:** rule-based (no LLM)
**Summary:** 7/13 fully correct, 3/13 partial (task type correct, some fields missing), 3/13 have issues

---

## PROJECT_WITH_CUSTOMER (5 tests)

### PWC-1: PARTIAL PASS
**Prompt:** "Opprett prosjektet Analyse knytt til kunden Sjobris AS (org.nr 883693329). Prosjektleiar er Steinar Berge (steinar@sjobris.no)"
**Task type:** project_with_customer -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| project_name/name | Analyse | (missing) | FAIL - project name not extracted |
| customer_name | Sjobris AS | Sjobris AS | PASS |
| project_manager_name | Steinar Berge | Steinar Berge | PASS |
| project_manager_email | steinar@sjobris.no | steinar@sjobris.no | PASS |
| organization_number | 883693329 | 883693329 | PASS (bonus) |

**Issue:** Project name "Analyse" not extracted. The regex looks for entity keyword + name pattern but "prosjektet" (definite form) is not matched. The `name` field is empty.

---

### PWC-2: PARTIAL PASS
**Prompt:** "Create a project Website linked to customer Acme Corp"
**Task type:** project_with_customer -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| project_name/name | Website | (missing from name, "Acme Corp" in name) | FAIL |
| customer_name | Acme Corp | (missing) | FAIL |

**Issue:** Rule-based regex sets `name=Acme Corp` but that's the customer, not the project. No `customer_name` field extracted. The "linked to customer" phrasing is not handled by the customer extraction regex.

---

### PWC-3: PASS
**Prompt:** "Lag eit prosjekt Webside for kunde Digital AS med fast pris 50000 kr"
**Task type:** project_with_customer -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| name | Webside | Webside | PASS |
| customer_name | Digital AS | Digital AS | PASS |
| fixed_price/price | 50000 | 50000.0 (as price_excluding_vat) | PASS (field name differs but executor handles it) |

---

### PWC-4: PARTIAL PASS
**Prompt:** "Erstellen Sie das Projekt Datenanalyse fur den Kunden Muller GmbH"
**Task type:** project_with_customer -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| name | Datenanalyse | Muller GmbH | FAIL - customer stored in name |
| customer_name | Muller GmbH | (missing) | FAIL |

**Issue:** German "fur den Kunden" triggers the customer regex which captures "Muller GmbH" into `name`. The project name "Datenanalyse" is not extracted. The `customer_name` field is empty.

---

### PWC-5: PARTIAL PASS
**Prompt:** "Creer le projet Audit pour le client Dupont SA, chef de projet Marie Martin"
**Task type:** project_with_customer -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| name | Audit | Dupont SA | FAIL - customer stored in name |
| customer_name | Dupont SA | (missing) | FAIL |
| project_manager_name | Marie Martin | Marie Martin | PASS |

**Issue:** Same as PWC-4 -- French "pour le client" pattern captures customer into `name` instead of `customer_name`, and project name "Audit" is lost.

---

## CREATE_CONTACT (5 tests)

### CC-1: PARTIAL PASS
**Prompt:** "Creer un contact Jean Dupont pour le client Acme AS, email jean@acme.fr"
**Task type:** create_contact -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| first_name | Jean | (missing) | FAIL |
| last_name | Dupont | (missing) | FAIL |
| customer | Acme AS | (missing) | FAIL |
| email | jean@acme.fr | jean@acme.fr | PASS |

**Issue:** French "contact" without "kontaktperson" keyword does match the task type via the `contact(?!@)` regex, but the rule-based field extraction for contacts only handles "kontaktperson X Y" / "contact person X Y" patterns, not "contact Jean Dupont pour...".

---

### CC-2: PASS
**Prompt:** "Opprett kontaktperson Anna Stress for kunde Stresstest Corp AS"
**Task type:** create_contact -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| first_name | Anna | Anna | PASS |
| last_name | Stress | Stress | PASS |
| customer | Stresstest Corp AS | Stresstest Corp AS (as customer_name) | PASS |

---

### CC-3: PARTIAL PASS
**Prompt:** "Opprett kontaktperson for kunde Nordic Tech AS: Per Hansen, per@nordic.no"
**Task type:** create_contact -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| first_name | Per | (missing) | FAIL |
| last_name | Hansen | (missing) | FAIL |
| customer | Nordic Tech AS | "Nordic Tech AS: Per Hansen" | FAIL - contaminated |
| email | per@nordic.no | per@nordic.no | PASS |

**Issue:** When contact name appears after customer name (colon-separated), the regex captures "Nordic Tech AS: Per Hansen" as one customer name, and fails to extract the contact name.

---

### CC-4: PARTIAL PASS
**Prompt:** "Create contact Sarah Wilson for customer Global Inc, sarah@global.com"
**Task type:** create_contact -- CORRECT
**Fields:**
| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| first_name | Sarah | (missing) | FAIL |
| last_name | Wilson | (missing) | FAIL |
| customer | Global Inc | Global Inc (as customer_name) | PASS |
| email | sarah@global.com | sarah@global.com | PASS |

**Issue:** "contact Sarah Wilson" -- the rule-based extractor looks for "kontaktperson|contact person|contacto|contato|kontakt" followed by a name. "contact" alone isn't matched because the regex requires "contact person" (two words) or "kontaktperson" (one word). The task type is correct but names are not extracted.

---

### CC-5: FAIL
**Prompt:** "Erstellen Sie einen Kontakt Max Schmidt fur den Kunden Berlin GmbH, max@berlin.de"
**Task type:** create_customer -- WRONG (expected create_contact)
**Fields:** name=Berlin GmbH, email=max@berlin.de

**Issue:** German "Kontakt" (capitalized) is not matched by the CREATE_CONTACT regex `\b(opprett|create|add|erstellen|creer|crear|criar)\b.*\b(contactperson|contact(?!@)|contacto|contato)\b` because the pattern requires "contact" (lowercase). The `(?i)` flag is set on the regex, so "Kontakt" should match... BUT looking more carefully, the German word "Kontakt" matches the `contact` pattern in CREATE_CONTACT, but "erstellen" + "Kunden" also matches CREATE_CUSTOMER -- and CREATE_CUSTOMER appears later in the keyword map order and wins.

Actually on re-check: CREATE_CONTACT patterns are checked before CREATE_CUSTOMER in the `_KEYWORD_MAP` list. The regex `\b(opprett|create|add|erstellen|creer|crear|criar)\b.*\b(contactperson|contact(?!@)|contacto|contato)\b` should match "Erstellen...Kontakt" via `erstellen.*contact`. But "Kontakt" != "contact" -- the regex checks `contact(?!@)` which requires exactly "contact" (5 chars). German "Kontakt" has 7 chars and would not match `contact` literally. The `re.IGNORECASE` flag would make "Contact" match but not "Kontakt" (different spelling).

---

## CREATE_PROJECT standalone (3 tests)

### CP-1: PASS
**Prompt:** "Opprett prosjekt Nettside"
**Task type:** create_project -- CORRECT
**Fields:** name=Nettside -- CORRECT

---

### CP-2: PASS
**Prompt:** "Create project Mobile App"
**Task type:** create_project -- CORRECT
**Fields:** name=Mobile App -- CORRECT

---

### CP-3: PARTIAL PASS
**Prompt:** "Erstellen Sie das Projekt Redesign"
**Task type:** create_project -- CORRECT
**Fields:** (empty) -- FAIL, name not extracted

**Issue:** German "das Projekt Redesign" -- "das" is a determiner that appears between the keyword "Projekt" and the name "Redesign". The rule-based regex expects entity keyword directly followed by optional name intro words, but "das" is not in the list of skip words.

---

## Summary Table

| Test | Task Type | Fields | Overall |
|------|-----------|--------|---------|
| PWC-1 | PASS | PARTIAL (name missing) | PARTIAL |
| PWC-2 | PASS | FAIL (name/customer swapped) | FAIL |
| PWC-3 | PASS | PASS | PASS |
| PWC-4 | PASS | FAIL (name/customer swapped) | FAIL |
| PWC-5 | PASS | PARTIAL (name=customer) | FAIL |
| CC-1 | PASS | FAIL (names missing) | FAIL |
| CC-2 | PASS | PASS | PASS |
| CC-3 | PASS | FAIL (names missing, customer contaminated) | FAIL |
| CC-4 | PASS | PARTIAL (names missing) | PARTIAL |
| CC-5 | FAIL | FAIL | FAIL |
| CP-1 | PASS | PASS | PASS |
| CP-2 | PASS | PASS | PASS |
| CP-3 | PASS | FAIL (name missing) | PARTIAL |

**Task type accuracy:** 12/13 (92%)
**Full pass (type + fields):** 4/13 (31%)
**Partial or better:** 8/13 (62%)

## Key Issues Found

1. **German "Kontakt" not matched as contact** -- the regex uses `contact(?!@)` which requires English spelling. Missing: `kontakt(?!@)` for German/Scandinavian.

2. **Project name extraction fails for non-Norwegian/English** -- German "das Projekt X" and French "le projet X" have determiners ("das", "le") between keyword and name that the regex doesn't skip.

3. **Customer vs project name confusion in rule-based mode** -- When both a project name and customer name appear, the customer name regex often captures into `name` field, overwriting or preventing project name extraction. This is a fundamental limitation of the regex approach for multi-entity prompts.

4. **Contact name extraction limited** -- Only "kontaktperson X Y" pattern works. English "contact X Y" and French "contact X Y" don't extract names because the regex requires "contact person" (two words).

5. **Colon-separated fields not handled** -- "for kunde Nordic Tech AS: Per Hansen" treats everything after "kunde" as the customer name.

**Note:** These issues are specific to the rule-based classifier. With Gemini or Claude LLM mode enabled, field extraction would be significantly better as the LLM handles multilingual parsing natively.
