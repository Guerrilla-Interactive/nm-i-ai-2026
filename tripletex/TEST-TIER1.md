# Tier 1 Classifier Test Results

**Date:** 2026-03-20 04:40
**Mode:** Rule-based (no LLM env vars)
**Total:** 36/46 passed (78%)

## Summary by Task Type

| Task Type | Passed | Total | Languages Tested |
|-----------|--------|-------|------------------|
| create_employee | 5 | 8 | de, en, es, fr, nb, nn, pt |
| update_employee | 2 | 3 | de, en, nb |
| delete_employee | 3 | 3 | en, fr, nb |
| set_employee_roles | 2 | 3 | en, nb |
| create_customer | 6 | 7 | de, en, es, fr, nb, pt |
| update_customer | 3 | 3 | en, fr, nb |
| create_product | 4 | 4 | de, en, fr, nb |
| create_invoice | 1 | 4 | de, en, fr, nb |
| create_department | 6 | 6 | de, en, es, fr, nb, pt |
| create_project | 4 | 5 | de, en, es, fr, nb |

## Detailed Results

### create_employee

**[PASS]** `[nb]` Opprett en ansatt med navn Ola Nordmann, e-post ola@example.com

- Classified as: `create_employee` (confidence: 0.6)
- Fields: ```{
  "name": "Ola Nordmann",
  "first_name": "Ola",
  "last_name": "Nordmann",
  "email": "ola@example.com"
}```

**[FAIL]** `[nn]` Opprett ein tilsett med namn Kari Bergström

- Classified as: `create_employee` (confidence: 0.6)
- Field issue: MISSING first_name (expected: 'Kari')
- Field issue: MISSING last_name (expected: 'Bergström')
- Fields: ```{
  "name": "Kari Bergström"
}```

**[PASS]** `[en]` Create an employee named John Smith with email john@smith.com

- Classified as: `create_employee` (confidence: 0.6)
- Fields: ```{
  "name": "John Smith",
  "first_name": "John",
  "last_name": "Smith",
  "email": "john@smith.com"
}```

**[FAIL]** `[de]` Erstellen Sie einen Mitarbeiter namens Hans Müller

- Classified as: `create_employee` (confidence: 0.6)
- Field issue: MISSING first_name (expected: 'Hans')
- Field issue: MISSING last_name (expected: 'Müller')
- Fields: ```{
  "name": "Hans Müller"
}```

**[PASS]** `[fr]` Créer un employé appelé Pierre Dupont

- Classified as: `create_employee` (confidence: 0.6)
- Fields: ```{
  "name": "Pierre Dupont",
  "first_name": "Pierre",
  "last_name": "Dupont"
}```

**[FAIL]** `[es]` Crear un empleado llamado Carlos García

- Classified as: `create_employee` (confidence: 0.6)
- Field issue: MISSING first_name (expected: 'Carlos')
- Field issue: MISSING last_name (expected: 'García')
- Fields: ```{
  "name": "Carlos García"
}```

**[PASS]** `[pt]` Criar um funcionário chamado João Silva

- Classified as: `create_employee` (confidence: 0.6)
- Fields: ```{
  "name": "João Silva",
  "first_name": "João",
  "last_name": "Silva"
}```

**[PASS]** `[nb]` Opprett ansatt med fornavn Emma og etternavn Wilson, e-post emma@test.no

- Classified as: `create_employee` (confidence: 0.6)
- Fields: ```{
  "first_name": "Emma",
  "last_name": "Wilson",
  "email": "emma@test.no"
}```

### update_employee

**[PASS]** `[nb]` Oppdater ansatt Per Hansen med ny e-post per@ny.no

- Classified as: `update_employee` (confidence: 0.6)
- Fields: ```{
  "first_name": "Per",
  "last_name": "Hansen",
  "email": "per@ny.no"
}```

**[PASS]** `[en]` Update employee Jane Doe with phone +47 912 34 567

- Classified as: `update_employee` (confidence: 0.6)
- Fields: ```{
  "first_name": "Jane",
  "last_name": "Doe",
  "phone": "+47 912 34 567"
}```

**[FAIL]** `[de]` Ändern Mitarbeiter Fritz Weber

- Classified as: `update_employee` (confidence: 0.6)
- Field issue: MISSING first_name (expected: 'Fritz')
- Field issue: MISSING last_name (expected: 'Weber')
- Fields: ```{}```

### delete_employee

**[PASS]** `[nb]` Slett ansatt Ola Nordmann

- Classified as: `delete_employee` (confidence: 0.6)
- Fields: ```{
  "first_name": "Ola",
  "last_name": "Nordmann"
}```

**[PASS]** `[en]` Delete employee John Smith

- Classified as: `delete_employee` (confidence: 0.6)
- Fields: ```{
  "first_name": "John",
  "last_name": "Smith"
}```

**[PASS]** `[fr]` Supprimer employé Pierre Dupont

- Classified as: `delete_employee` (confidence: 0.6)
- Fields: ```{
  "first_name": "Pierre",
  "last_name": "Dupont"
}```

### set_employee_roles

**[PASS]** `[nb]` Sett ansatt Erik Berg som administrator

- Classified as: `set_employee_roles` (confidence: 0.6)
- Fields: ```{
  "user_type": "EXTENDED",
  "first_name": "Erik",
  "last_name": "Berg"
}```

**[PASS]** `[en]` Set employee John Doe as standard user with no access

- Classified as: `set_employee_roles` (confidence: 0.6)
- Fields: ```{
  "user_type": "STANDARD",
  "first_name": "John",
  "last_name": "Doe"
}```

**[FAIL]** `[nb]` Endre rolle for ansatt Kari Olsen til standard

- Classified as: `update_employee` (confidence: 0.6)
- Fields: ```{
  "first_name": "Kari",
  "last_name": "Olsen"
}```

### create_customer

**[PASS]** `[nb]` Opprett kunde Fjord Konsult AS med org.nr 987654321, e-post post@fjord.no

- Classified as: `create_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Fjord Konsult AS",
  "email": "post@fjord.no",
  "organization_number": "987654321"
}```

**[PASS]** `[en]` Create customer Nordic Tech Ltd with email info@nordic.com

- Classified as: `create_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Nordic Tech Ltd",
  "email": "info@nordic.com"
}```

**[FAIL]** `[de]` Erstellen Sie einen Kunden namens Schmidt GmbH mit der Organisationsnummer 12345

- Classified as: `create_customer` (confidence: 0.6)
- Field issue: MISSING organization_number (expected: '123456789')
- Fields: ```{
  "name": "Schmidt GmbH"
}```

**[PASS]** `[fr]` Créer un client appelé Dupont SARL

- Classified as: `create_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Dupont SARL"
}```

**[PASS]** `[es]` Crear un cliente llamado Empresa SA

- Classified as: `create_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Empresa SA"
}```

**[PASS]** `[pt]` Criar um cliente chamado Brasil Corp

- Classified as: `create_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Brasil Corp"
}```

**[PASS]** `[nb]` Opprett kunde Bergen Shipping AS med adresse Storgata 5, 5003 Bergen

- Classified as: `create_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Bergen Shipping AS",
  "address_line1": "Storgata 5",
  "postal_code": "5003",
  "city": "Bergen"
}```

### update_customer

**[PASS]** `[nb]` Oppdater kunde Fjord AS med ny e-post info@fjord.no

- Classified as: `update_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Fjord AS",
  "email": "info@fjord.no"
}```

**[PASS]** `[en]` Update customer Nordic Tech AS email to info@nordictech.no

- Classified as: `update_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Nordic Tech AS",
  "email": "info@nordictech.no"
}```

**[PASS]** `[fr]` Modifier client Dupont SARL

- Classified as: `update_customer` (confidence: 0.6)
- Fields: ```{
  "name": "Dupont SARL"
}```

### create_product

**[PASS]** `[nb]` Opprett produkt Konsulenttjeneste med pris 1500 kr eks. mva, 25% MVA

- Classified as: `create_product` (confidence: 0.6)
- Fields: ```{
  "name": "Konsulenttjeneste",
  "price_excluding_vat": 1500.0,
  "vat_percentage": 25
}```

**[PASS]** `[en]` Create a product called Premium Support with price 2500 NOK

- Classified as: `create_product` (confidence: 0.6)
- Fields: ```{
  "name": "Premium Support",
  "price_excluding_vat": 2500.0
}```

**[PASS]** `[de]` Erstellen Sie das Produkt Datenberatung mit Produktnummer 5524, Preis 22550 NOK,

- Classified as: `create_product` (confidence: 0.6)
- Fields: ```{
  "name": "Datenberatung",
  "price_excluding_vat": 22550.0,
  "vat_percentage": 25,
  "number": "5524"
}```

**[PASS]** `[fr]` Créer un produit appelé Analyse avec prix 3000 NOK

- Classified as: `create_product` (confidence: 0.6)
- Fields: ```{
  "name": "Analyse",
  "price_excluding_vat": 3000.0
}```

### create_invoice

**[FAIL]** `[nb]` Opprett faktura til kunde Acme AS: 3 stk Frakttjeneste til 2500 kr, 1 stk Emball

- Classified as: `invoice_existing_customer` (confidence: 0.6)
- Fields: ```{
  "price_excluding_vat": 2500.0,
  "customer_name": "Acme AS",
  "lines": [
    {
      "description": "Frakttjeneste",
      "quantity": 3,
      "unit_price": 2500.0
    },
    {
      "description": "Emballasje",
      "quantity": 1,
      "unit_price": 150.0
    }
  ]
}```

**[FAIL]** `[en]` Create an invoice for customer NewCo Ltd: 5 pcs Widget at 100 NOK

- Classified as: `invoice_existing_customer` (confidence: 0.6)
- Fields: ```{
  "price_excluding_vat": 100.0,
  "customer_name": "NewCo Ltd",
  "lines": [
    {
      "description": "Widget",
      "quantity": 5,
      "unit_price": 100.0
    }
  ]
}```

**[FAIL]** `[de]` Erstellen Rechnung für Kunde Müller GmbH

- Classified as: `invoice_existing_customer` (confidence: 0.6)
- Fields: ```{
  "customer_name": "Müller GmbH"
}```

**[PASS]** `[fr]` Créer une facture pour client Dupont SA

- Classified as: `create_invoice` (confidence: 0.6)
- Fields: ```{
  "customer_name": "Dupont SA"
}```

### create_department

**[PASS]** `[nb]` Opprett avdeling Markedsføring med avdelingsnummer 40

- Classified as: `create_department` (confidence: 0.6)
- Fields: ```{
  "name": "Markedsføring",
  "department_number": "40"
}```

**[PASS]** `[en]` Create department Finance

- Classified as: `create_department` (confidence: 0.6)
- Fields: ```{
  "name": "Finance"
}```

**[PASS]** `[de]` Erstellen Abteilung Vertrieb

- Classified as: `create_department` (confidence: 0.6)
- Fields: ```{
  "name": "Vertrieb"
}```

**[PASS]** `[fr]` Créer un département appelé Marketing

- Classified as: `create_department` (confidence: 0.6)
- Fields: ```{
  "name": "Marketing"
}```

**[PASS]** `[es]` Crear departamento Ventas

- Classified as: `create_department` (confidence: 0.6)
- Fields: ```{
  "name": "Ventas"
}```

**[PASS]** `[pt]` Criar departamento Recursos Humanos

- Classified as: `create_department` (confidence: 0.6)
- Fields: ```{
  "name": "Recursos Humanos"
}```

### create_project

**[PASS]** `[nb]` Opprett prosjekt Nettside Redesign, start 2026-04-01

- Classified as: `create_project` (confidence: 0.6)
- Fields: ```{
  "name": "Nettside Redesign",
  "start_date": "2026-04-01"
}```

**[PASS]** `[en]` Create project Website Redesign

- Classified as: `create_project` (confidence: 0.6)
- Fields: ```{
  "name": "Website Redesign"
}```

**[FAIL]** `[de]` Erstellen Projekt Datenanalyse

- Classified as: `create_project` (confidence: 0.6)
- Field issue: MISSING name (expected: 'Datenanalyse')
- Fields: ```{}```

**[PASS]** `[fr]` Créer projet Transformation Digitale

- Classified as: `create_project` (confidence: 0.6)
- Fields: ```{
  "name": "Transformation Digitale"
}```

**[PASS]** `[es]` Crear proyecto Migración Cloud

- Classified as: `create_project` (confidence: 0.6)
- Fields: ```{
  "name": "Migración Cloud"
}```

## Failures

- **[nn] create_employee**: Opprett ein tilsett med namn Kari Bergström
  - MISSING first_name (expected: 'Kari')
  - MISSING last_name (expected: 'Bergström')
- **[de] create_employee**: Erstellen Sie einen Mitarbeiter namens Hans Müller
  - MISSING first_name (expected: 'Hans')
  - MISSING last_name (expected: 'Müller')
- **[es] create_employee**: Crear un empleado llamado Carlos García
  - MISSING first_name (expected: 'Carlos')
  - MISSING last_name (expected: 'García')
- **[de] update_employee**: Ändern Mitarbeiter Fritz Weber
  - MISSING first_name (expected: 'Fritz')
  - MISSING last_name (expected: 'Weber')
- **[nb] set_employee_roles**: Endre rolle for ansatt Kari Olsen til standard
  - Type mismatch: expected `set_employee_roles`, got `update_employee`
- **[de] create_customer**: Erstellen Sie einen Kunden namens Schmidt GmbH mit der Organisationsnummer 12345
  - MISSING organization_number (expected: '123456789')
- **[nb] create_invoice**: Opprett faktura til kunde Acme AS: 3 stk Frakttjeneste til 2500 kr, 1 stk Emball
  - Type mismatch: expected `create_invoice`, got `invoice_existing_customer`
- **[en] create_invoice**: Create an invoice for customer NewCo Ltd: 5 pcs Widget at 100 NOK
  - Type mismatch: expected `create_invoice`, got `invoice_existing_customer`
- **[de] create_invoice**: Erstellen Rechnung für Kunde Müller GmbH
  - Type mismatch: expected `create_invoice`, got `invoice_existing_customer`
- **[de] create_project**: Erstellen Projekt Datenanalyse
  - MISSING name (expected: 'Datenanalyse')
