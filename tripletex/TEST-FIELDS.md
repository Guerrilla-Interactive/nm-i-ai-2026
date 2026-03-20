# Field Extraction Test Results

**Date:** 2026-03-20
**Classifier mode:** rule-based (no LLM)
**Tests passed:** 4/10
**Fields correct:** 23/31

## Per-Test Results

### Test 1: PASS
**Prompt:** `Erstellen Sie das Produkt Datenberatung mit der Produktnummer 5524. Der Preis be...`
**Task type:** create_product (expected: create_product) OK
**Extracted fields:** `{"name": "Datenberatung", "price_excluding_vat": 22550.0, "vat_percentage": 25, "number": "5524"}`

### Test 2: FAIL
**Prompt:** `Erstellen Sie den Kunden Grünfeld GmbH mit der Organisationsnummer 835026434. Di...`
**Task type:** create_customer (expected: create_customer) OK
**Mismatches:**
-   organization_number: got=None, expected='835026434'
-   address_line1: got='ist Fjordveien 105', expected='Fjordveien 105'
**Extracted fields:** `{"name": "Grünfeld GmbH", "address_line1": "ist Fjordveien 105", "postal_code": "3015", "city": "Drammen"}`

### Test 3: FAIL
**Prompt:** `Opprett prosjektet Analyse knytt til kunden Sjøbris AS (org.nr 883693329). Prosj...`
**Task type:** project_with_customer (expected: project_with_customer) OK
**Mismatches:**
-   project_name: got=None, expected='Analyse'
**Extracted fields:** `{"email": "steinar@sjobris.no", "organization_number": "883693329", "customer_name": "Sjøbris AS", "project_manager_name": "Steinar Berge", "project_manager_email": "steinar@sjobris.no"}`

### Test 4: FAIL
**Prompt:** `Le client Colline SARL (nº org. 850491941) a une facture impayée de 10550 NOK ho...`
**Task type:** invoice_with_payment (expected: invoice_with_payment) OK
**Mismatches:**
-   customer_name: got='Colline SARL (nº org', expected='Colline SARL'
-   lines[0].unit_price: NO LINES EXTRACTED
-   lines[0].description: NO LINES EXTRACTED
**Extracted fields:** `{"price_excluding_vat": 10550.0, "organization_number": "850491941", "customer_name": "Colline SARL (nº org", "amount": 10550.0}`

### Test 5: PASS
**Prompt:** `Vi har en ny ansatt som heter Astrid Strand, født 4. May 1986. Opprett vedkommen...`
**Task type:** create_employee (expected: create_employee) OK
**Extracted fields:** `{"name": "Astrid Strand", "first_name": "Astrid", "last_name": "Strand", "email": "astrid.strand@example.com"}`

### Test 6: FAIL
**Prompt:** `Lag faktura til kunde Nordfjord AS: 2 stk Konsulenttjeneste til 1500 kr...`
**Task type:** invoice_existing_customer (expected: create_invoice) MISMATCH
**Mismatches:**
- TASK_TYPE: got=invoice_existing_customer, expected=create_invoice
**Extracted fields:** `{"price_excluding_vat": 1500.0, "customer_name": "Nordfjord AS", "lines": [{"description": "Konsulenttjeneste", "quantity": 2, "unit_price": 1500.0}]}`

### Test 7: PASS
**Prompt:** `Opprett ein ny avdeling som heiter Marknadsføring...`
**Task type:** create_department (expected: create_department) OK
**Extracted fields:** `{"name": "Marknadsføring"}`

### Test 8: PASS
**Prompt:** `Opprett en ansatt med navn Ola Nordmann, ola@example.org. Han skal være kontoadm...`
**Task type:** create_employee (expected: create_employee) OK
**Extracted fields:** `{"name": "Ola Nordmann", "first_name": "Ola", "last_name": "Nordmann", "email": "ola@example.org", "user_type": "ADMINISTRATOR"}`

### Test 9: FAIL
**Prompt:** `Create three departments in Tripletex: Utvikling, Innkjøp, and Salg....`
**Task type:** unknown (expected: create_department) MISMATCH
**Note:** Rule-based cannot do batch. Check task_type only.
**Mismatches:**
- TASK_TYPE: got=unknown, expected=create_department
**Extracted fields:** `{}`

### Test 10: FAIL
**Prompt:** `Créer un contact Jean Dupont pour le client Acme AS, email jean@acme.fr...`
**Task type:** create_contact (expected: create_contact) OK
**Mismatches:**
-   first_name: got=None, expected='Jean'
-   last_name: got=None, expected='Dupont'
**Extracted fields:** `{"email": "jean@acme.fr"}`

## Analysis

6 test(s) failed. Issues found:

- **Test 2:**   organization_number: got=None, expected='835026434';   address_line1: got='ist Fjordveien 105', expected='Fjordveien 105'
- **Test 3:**   project_name: got=None, expected='Analyse'
- **Test 4:**   customer_name: got='Colline SARL (nº org', expected='Colline SARL';   lines[0].unit_price: NO LINES EXTRACTED;   lines[0].description: NO LINES EXTRACTED
- **Test 6:** TASK_TYPE: got=invoice_existing_customer, expected=create_invoice
- **Test 9:** TASK_TYPE: got=unknown, expected=create_department
- **Test 10:**   first_name: got=None, expected='Jean';   last_name: got=None, expected='Dupont'

These failures indicate areas where the rule-based regex patterns need improvement,
or where an LLM classifier (Gemini/Claude) would perform better.