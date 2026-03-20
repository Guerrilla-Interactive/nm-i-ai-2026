# Grader Prompt Patterns Analysis

**Generated:** 2026-03-20
**Competition:** NM i AI 2026 -- Tripletex Accounting Agent
**Scope:** 30 task types x 7 languages x 8 data sets = up to 1680 variants

---

## Table of Contents

1. [Methodology](#methodology)
2. [Language Patterns](#language-patterns)
3. [Data Patterns](#data-patterns)
4. [Task-by-Task Analysis with Example Prompts](#task-by-task-analysis)
5. [Multi-Step Task Complexity](#multi-step-task-complexity)
6. [Potential Gotchas](#potential-gotchas)
7. [Coverage Gaps](#coverage-gaps)

---

## Methodology

Sources analyzed:
- Cloud Run logs: ~150 requests across 12 hours (mix of grader + our tests)
- Confirmed grader requests (IP 34.34.240.x, user-agent python-httpx/0.28.1): 4 confirmed
- GRADER-LOG.md: 17 documented request/response pairs
- GRADER-ANALYSIS.md: detailed analysis of 2 grader requests
- classifier.py: few-shot examples revealing expected patterns

### Confirmed Grader Prompts (from production)

| # | Language | Prompt |
|---|----------|--------|
| 1 | nb | Lag faktura til kunde Nordfjord AS: 2 stk Konsulenttjeneste til 1500 kr |
| 2 | nn | Opprett prosjektet "Analyse Sjobris" knytt til kunden Sjobris AS (org.nr 883693329). Prosjektleiar er Steinar Berge (steinar@sjobris.no) |
| 3 | nn | Opprett ein ny avdeling som heiter Marknadsfoering |
| 4 | de | Erstellen Sie das Produkt "Datenberatung" mit der Produktnummer 5524. Der Preis betraegt 22550 NOK ohne MwSt., mit dem Steuersatz 25% |
| 5 | de | Erstellen Sie den Kunden Grunfeld GmbH mit der Organisationsnummer 835026434. Die Adresse ist Fjordveien 105, 3015 Drammen |
| 6 | en | Create three departments in Tripletex: "Utvikling", "Innkjop", and "Salg". |
| 7 | fr | Le client Colline SARL (no org. 850491941) a une facture impayee de 10550 NOK hors TVA pour "Heures de conseil". Enregistrer le paiement. |
| 8 | nb | Vi har en ny ansatt som heter Astrid Strand, fodt 4. May 1986. Opprett vedkommende som ansatt med e-post astrid.strand@e... |
| 9 | nb | Kunden Brattli AS (org.nr 909268265) har en utestaende faktura pa 31300 kr eksklusiv MVA for "Konsulenttimer". Registrer... |

---

## Language Patterns

### Norwegian Bokmal (nb)

**Verb patterns:**
- "Opprett" (Create) -- most common opener
- "Lag" (Make) -- used for invoices: "Lag faktura"
- "Registrer" (Register) -- for payments, travel expenses
- "Slett" (Delete) -- for deletion tasks
- "Oppdater" / "Endre" (Update/Change) -- for updates
- "Finn" (Find) -- for search
- "Sett" / "Gi" (Set/Give) -- for role assignment
- "Aktiver" (Activate) -- for module enablement
- "Fakturer" (Invoice) -- for project billing
- "Korriger" (Correct) -- for error correction

**Structural patterns:**
- "Opprett en ansatt med navn X, e-post Y" (Create employee named X, email Y)
- "Opprett kunde X AS med org.nr Y" (Create customer X AS with org no Y)
- "Lag faktura til kunde X: N stk Y til Z kr" (Make invoice for customer X: N pcs Y at Z kr)
- "Vi har en ny ansatt som heter X, fodt D. Opprett vedkommende som ansatt med e-post Y" (narrative style)
- "Kunden X (org.nr Y) har en utestaende faktura pa Z kr..." (narrative for invoice+payment)

**Key observations:**
- Grader uses narrative style: "Vi har en ny ansatt som heter..." rather than just "Opprett ansatt..."
- "Han/hun skal vaere kontoadministrator" for role specification inline with employee creation
- Birth dates: "fodt 4. May 1986" (mixed Norwegian/English month names!)
- "eksklusiv MVA" for VAT exclusion
- "betalt i sin helhet" for "paid in full"

### Norwegian Nynorsk (nn)

**Verb patterns:**
- "Opprett ein" (Create a, masculine/feminine)
- "Lag eit" (Make a, neuter)
- "Opprett ein tilsett" (Create an employee -- "tilsett" not "ansatt")
- "Opprett ein ny avdeling som heiter" (Create a new department called)

**Key differences from Bokmal:**
- "tilsett" instead of "ansatt" (employee)
- "heiter" instead of "heter" (is called)
- "knytt til" instead of "knyttet til" (linked to)
- "reiserekning" instead of "reiseregning" (travel expense)
- "Prosjektleiar" instead of "Prosjektleder" (project manager)
- "namn" instead of "navn" (name)
- "fraa" instead of "fra" (from)
- "ein" instead of "en" (a/an)
- "fodd" instead of "fodt" (born)
- "formaal" instead of "formal" (purpose)
- "avgrensa" instead of "begrenset" (restricted/limited)

**Structural patterns:**
- "Opprett ein tilsett med namn X, e-post Y"
- "Opprett prosjektet X knytt til kunden Y AS (org.nr Z). Prosjektleiar er A B (email)"
- "Opprett ein ny avdeling som heiter X"
- "Opprett reiserekning for tilsett X, dagsreise fraa Y til Z"
- "Ho skal ha avgrensa tilgang" (She should have restricted access)

### English (en)

**Verb patterns:**
- "Create" -- most common
- "Create a/an" -- with article
- "Add" -- for contacts: "Add a contact person"
- "Delete" / "Remove" -- for deletion
- "Update" / "Modify" -- for updates
- "Set" -- for roles: "Set employee X as..."
- "Register" -- for payments
- "Invoice" -- as verb: "Invoice customer X for..."
- "Perform" -- "Perform bank reconciliation"
- "Enable" -- "Enable the travel expense module"

**Structural patterns:**
- "Create an employee named X with email Y, starting Z"
- "Create three departments in Tripletex: X, Y, and Z."
- "Invoice customer X for N units of Y at Z NOK each"
- "Create an invoice for X for N hours Y at Z NOK/hr, already paid in full"
- "Register payment of X NOK on invoice Y"
- "Add a contact person X for customer Y, email Z"
- "Delete travel expense for employee X"
- "Create a project X linked to customer Y"
- "Set employee X as a standard user with no access"
- "Create a product called X with price Y NOK excluding VAT"
- "Year-end closing for 2025"
- "Perform bank reconciliation for March 2026"
- "Correct error in voucher 1234"

### German (de)

**Verb patterns:**
- "Erstellen Sie" (Create, formal) -- always formal "Sie" form
- "Erstellen Sie einen/eine/ein" (with article matching gender)
- "Loeschen Sie" (Delete)
- "Aktualisieren Sie" (Update)
- "Registrieren Sie" (Register)

**Structural patterns:**
- "Erstellen Sie einen Kunden namens X mit der Organisationsnummer Y. Die Adresse ist Z"
- "Erstellen Sie das Produkt X mit der Produktnummer Y. Der Preis betraegt Z NOK ohne MwSt., mit dem Steuersatz N%"
- "Erstellen Sie eine Abteilung namens X"
- "Erstellen Sie einen Mitarbeiter namens X, E-Mail Y"
- "Erstellen Sie eine Reisekostenabrechnung fuer Mitarbeiter X, Tagesreise von Y nach Z am D"
- "Erstellen Sie ein Projekt namens X"
- "Der Kunde X hat eine unbezahlte Rechnung ueber Y NOK fuer Z. Zahlung registrieren."

**Key vocabulary:**
- MwSt (Mehrwertsteuer) = VAT
- Steuersatz = tax rate
- Organisationsnummer = organization number
- Produktnummer = product number
- Reisekostenabrechnung = travel expense report
- Tagesreise = day trip
- Abteilung = department
- Mitarbeiter = employee
- Gutschrift = credit note
- Rechnung = invoice
- Zahlung = payment
- unbezahlte = unpaid

### French (fr)

**Verb patterns:**
- "Creer" (Create)
- "Creer un/une" (with article)
- "Le client X... Enregistrer le paiement" (narrative + imperative)
- "Supprimer" (Delete)
- "Modifier" / "Mettre a jour" (Update)

**Structural patterns:**
- "Le client X (no org. Y) a une facture impayee de Z NOK hors TVA pour 'description'. Enregistrer le paiement."
- "Creer un employe nomme X, email Y"
- "Creer un departement appele X"
- "Creer un contact X pour le client Y, email Z"
- "Creer un produit appele X avec le prix Y NOK hors TVA"

**Key vocabulary:**
- TVA (Taxe sur la valeur ajoutee) = VAT
- hors TVA = excluding VAT
- facture impayee = unpaid invoice
- paiement = payment
- no org. = org number (note: "no" not "nro")
- note de frais = travel expense
- avoir = credit note
- departement = department
- employe = employee
- client = customer

### Spanish (es)

**Verb patterns:**
- "Crear" (Create)
- "Crear un/una" (with article)
- "Registrar" (Register)
- "Eliminar" (Delete)
- "Actualizar" / "Modificar" (Update)

**Structural patterns (projected):**
- "Crear una factura para el cliente X por N unidades de Y a Z NOK cada una"
- "Crear un empleado llamado X, correo Y"
- "Crear un departamento llamado X"
- "Crear un producto llamado X con precio Y NOK sin IVA"
- "Registrar pago de X NOK en factura Y"
- "El cliente X (no org. Y) tiene una factura impaga de Z NOK sin IVA. Registrar el pago."
- "Crear factura para cliente existente X, N unidad(es) de Y a Z NOK"

**Key vocabulary:**
- IVA (Impuesto al Valor Agregado) = VAT
- sin IVA = excluding VAT
- factura impaga = unpaid invoice
- pago = payment
- gasto de viaje = travel expense
- nota de credito = credit note
- departamento = department
- empleado = employee
- cliente = customer
- factura = invoice

### Portuguese (pt)

**Verb patterns:**
- "Criar" (Create)
- "Criar um/uma" (with article)
- "Registrar" (Register)
- "Excluir" / "Remover" (Delete)
- "Atualizar" / "Modificar" (Update)

**Structural patterns (projected):**
- "Criar cliente X com numero de organizacao Y"
- "Criar um funcionario chamado X, email Y"
- "Criar um departamento chamado X"
- "Criar um produto chamado X com preco Y NOK sem IVA"
- "Criar um projeto chamado X para o cliente Y"
- "Registrar pagamento de X NOK na fatura Y"
- "O cliente X (no org. Y) tem uma fatura em aberto de Z NOK sem IVA. Registrar o pagamento."

**Key vocabulary:**
- IVA (Imposto sobre o Valor Acrescentado) = VAT
- sem IVA = excluding VAT
- fatura em aberto = unpaid invoice
- pagamento = payment
- despesa de viagem = travel expense
- nota de credito = credit note
- departamento = department
- funcionario = employee
- cliente = customer

---

## Data Patterns

### Names

**Norwegian names (most common in data sets):**
- First names: Ola, Kari, Per, Astrid, Steinar, Randi, Erik
- Last names: Nordmann, Hansen, Strand, Berge, Brekke, Berg
- Full names: "Ola Nordmann", "Kari Nordmann", "Per Hansen", "Astrid Strand"

**German-style names:**
- "Hans Mueller", "Gruenfeld GmbH"

**French-style names:**
- "Jean Dupont", "Pierre Dupont", "Colline SARL"

**Company name suffixes:**
- Norwegian: AS, ASA
- German: GmbH, AG
- French: SARL, SA
- Spanish: SL, SA
- Portuguese: Ltda, SA
- English: Ltd, Inc, Corp

**Observed company names:**
- Nordfjord AS, Sjobris AS, Fjord Konsult AS, Nordic Tech AS, Acme AS, Digital AS
- Gruenfeld GmbH, Mueller GmbH
- Colline SARL
- Silva Ltda
- Acme Corp, Stresstest Corp AS
- Brattli AS
- TestCorp AS, Testfirma AS, Fjorddata AS, Fjord Shipping AS

### Organization Numbers

**Format:** 9 digits, always numeric
**Examples observed:** 883693329, 835026434, 850491941, 987654321, 123456789, 909268265
**Pattern:** Always prefixed with "org.nr", "Organisationsnummer", "no org.", "numero de organizacao"
**Note:** Some prompts include org numbers, some don't -- the grader varies

### Addresses

**Norwegian format observed:**
- "Fjordveien 105, 3015 Drammen"
- "Storgata 5, 0001 Oslo"
- Pattern: `<Street> <Number>, <PostalCode> <City>`
- Postal codes: 4 digits (Norwegian standard)
- Always Norwegian addresses even for German/French prompts

### Prices and Amounts

**Formats observed:**
- "1500 kr" (Norwegian krone, short)
- "22550 NOK" (formal)
- "500 NOK each" (English per-unit)
- "1500 NOK/hr" (per hour)
- "10550 NOK hors TVA" (French, excl. VAT)
- "5000 NOK" (round numbers)
- "31300 kr eksklusiv MVA" (Bokmal, excl. VAT)
- "50000 kr" (fixed price)
- "1200 kr" (per unit)
- "3000 NOK" (per unit)

**Amount patterns:**
- Round numbers common: 500, 1200, 1500, 2500, 3000, 5000, 10550, 22550, 31300, 50000
- Always NOK (Norwegian Krone) regardless of language
- "kr" for Norwegian prompts, "NOK" for international
- "eks. mva" / "eksklusiv MVA" / "ohne MwSt." / "hors TVA" / "excluding VAT" / "sin IVA" / "sem IVA" for VAT exclusion

### Dates

**Formats observed:**
- "19. mars 2026" (Norwegian textual)
- "2026-04-01" (ISO)
- "15.03.2026" (European DD.MM.YYYY)
- "March 1st 2026" / "March 20 2026" (English)
- "4. May 1986" (mixed Norwegian/English! -- birth date)
- "19. Maerz 2026" (German)
- "am 19. Maerz 2026" (German with preposition)
- "01/04/2026" (European slash format)

**Date gotcha:** Grader has been observed mixing Norwegian date structure with English month names ("4. May 1986"). The classifier must handle mixed-language dates.

### Email Formats

**Patterns:**
- firstname@example.org (ola@example.org)
- firstname.lastname@example.org (astrid.strand@example.org)
- firstname@company.no (steinar@sjobris.no, post@fjord.no)
- firstname@lastname.de (hans@mueller.de)
- firstname@company.fr (jean@acme.fr)
- post@company.no (generic)
- info@company.no (generic)

### Phone Formats

**Patterns observed:**
- "91234567" (8-digit Norwegian, no spaces)
- "99887766" (8-digit Norwegian, no spaces)
- "+47 912 34 567" (international format with spaces)

### VAT Rates

**Values observed:** 25%, 15%, 12%, 0%
**Norwegian standard:** 25% (general), 15% (food), 12% (transport/cinema), 0% (exempt)
**How specified:**
- "25% MVA" (nb)
- "mit dem Steuersatz 25%" (de)
- "hors TVA" (fr -- implies VAT should be applied at standard rate)
- "excluding VAT" (en)
- "eks. mva" (nb)

### Quantities

**Patterns:**
- "2 stk" / "1 stk" / "3 stk" (Norwegian)
- "5 units" / "1 unit" (English)
- "10 timer" / "3 hours" (hours)
- "N unidades" (Spanish)
- "N unidade(s)" (Portuguese)
- "N Stueck" (German)

---

## Task-by-Task Analysis

### Tier 1 -- Foundational (x1 multiplier)

#### 1. CREATE_EMPLOYEE

**nb:** "Opprett en ansatt med navn Ola Nordmann, e-post ola@example.org, telefon 91234567, fodt 1990-05-15, startdato 2026-04-01"
**nb (narrative):** "Vi har en ny ansatt som heter Astrid Strand, fodt 4. May 1986. Opprett vedkommende som ansatt med e-post astrid.strand@example.org"
**nb (with role):** "Opprett en ansatt med navn Ola Nordmann, ola@example.org. Han skal vaere kontoadministrator."
**nn:** "Opprett ein tilsett med namn Kari Berge, e-post kari@berge.no, telefon 91234567"
**nn (with role):** "Opprett ein tilsett som heiter Kari Berge med e-post kari@berge.no. Ho skal ha avgrensa tilgang."
**en:** "Create an employee named John Smith with email john@smith.com, starting March 1st 2026"
**de:** "Erstellen Sie einen Mitarbeiter namens Hans Mueller, E-Mail hans@mueller.de"
**fr:** "Creer un employe nomme Pierre Dupont, email pierre@dupont.fr"
**es:** "Crear un empleado llamado Juan Garcia, correo juan@garcia.es, telefono +47 91234567"
**pt:** "Criar um funcionario chamado Carlos Silva, email carlos@silva.pt, inicio em 01/04/2026"

**Key fields:** first_name, last_name, email, phone, date_of_birth, start_date, user_type
**Gotchas:**
- Narrative style prompts ("Vi har en ny ansatt som heter...")
- Role specification inline ("Han skal vaere kontoadministrator")
- Birth date vs. start date confusion
- Mixed-language month names in dates
- "vedkommende" (the person in question) as pronoun

#### 2. UPDATE_EMPLOYEE

**nb:** "Oppdater telefonnummer for ansatt Ola Nordmann til 99887766"
**nb:** "Endre ansatt Kari Nordmann sin telefon til 99887766"
**nn:** "Oppdater tilsett Kari Nordmann med ny telefon 99887766"
**en:** "Update employee John Smith's phone to +47 912 34 567"
**de:** "Aktualisieren Sie die Telefonnummer von Mitarbeiter Hans Mueller auf 99887766"
**fr:** "Modifier le telephone de l'employe Pierre Dupont en 99887766"
**es:** "Actualizar el telefono del empleado Juan Garcia a 99887766"
**pt:** "Atualizar o telefone do funcionario Carlos Silva para 99887766"

**Key fields:** employee_identifier (name), field to update, new value

#### 3. DELETE_EMPLOYEE

**nb:** "Slett ansatt Ola Nordmann"
**nn:** "Slett tilsett Kari Berge"
**en:** "Delete employee John Smith"
**de:** "Loeschen Sie den Mitarbeiter Hans Mueller"
**fr:** "Supprimer l'employe Pierre Dupont"
**es:** "Eliminar al empleado Juan Garcia"
**pt:** "Excluir o funcionario Carlos Silva"

**Key fields:** employee_identifier (name)

#### 4. SET_EMPLOYEE_ROLES

**nb:** "Sett ansatt Ola Nordmann som kontoadministrator"
**nb:** "Gi ansatt Per Hansen rollen som administrator"
**nn:** "Opprett ein tilsett... Ho skal ha avgrensa tilgang." (inline with creation)
**en:** "Set employee John Smith as a standard user with no access"
**de:** "Setzen Sie Mitarbeiter Hans Mueller als Administrator"
**fr:** "Definir l'employe Pierre Dupont comme administrateur"
**es:** "Establecer al empleado Juan Garcia como usuario estandar"
**pt:** "Definir o funcionario Carlos Silva como administrador"

**Key fields:** employee_identifier, user_type (ADMINISTRATOR, STANDARD, RESTRICTED, NO_ACCESS)
**Gotcha:** Can appear inline with CREATE_EMPLOYEE ("Opprett... Han skal vaere kontoadministrator")

#### 5. CREATE_CUSTOMER

**nb:** "Opprett kunde Fjord Konsult AS med org.nr 987654321, e-post post@fjord.no, adresse Storgata 5, 0001 Oslo"
**nb:** "Opprett en kunde med navn Fjord Shipping AS, e-post kontakt@fjord.no"
**nn:** "Opprett ein kunde Nordfjord AS med e-post post@nordfjord.no"
**en:** "Create customer Nordic Tech AS with email info@nordictech.no"
**de:** "Erstellen Sie den Kunden Gruenfeld GmbH mit der Organisationsnummer 835026434. Die Adresse ist Fjordveien 105, 3015 Drammen"
**fr:** "Creer un client Colline SARL avec le numero d'organisation 850491941"
**es:** "Crear un cliente llamado Empresa SA con numero de organizacion 123456789"
**pt:** "Criar cliente Silva Ltda com numero de organizacao 123456789"

**Key fields:** name, organization_number, email, address_line1, postal_code, city
**Gotcha:** German prompt gives full address in one sentence with periods and commas

#### 6. UPDATE_CUSTOMER

**nb:** "Oppdater e-post for kunde Fjord Konsult AS til ny@fjord.no"
**en:** "Update customer Nordic Tech AS email to info@nordictech.no"
**de:** "Aktualisieren Sie die E-Mail des Kunden Gruenfeld GmbH auf info@gruenfeld.de"
**fr:** "Modifier l'email du client Colline SARL en contact@colline.fr"
**es:** "Actualizar el correo del cliente Empresa SA a info@empresa.es"
**pt:** "Atualizar o email do cliente Silva Ltda para contato@silva.pt"

**Key fields:** customer_identifier, field to update, new value

#### 7. CREATE_PRODUCT

**nb:** "Opprett produkt Konsulenttjeneste med pris 1500 kr eks. mva, 25% MVA"
**nb:** "Opprett produkt Konsulenttjeneste med produktnummer 1234, pris 1500 kr eks. mva, 25% MVA"
**en:** "Create a product called Premium Support with price 2500 NOK excluding VAT"
**de:** "Erstellen Sie das Produkt Datenberatung mit der Produktnummer 5524. Der Preis betraegt 22550 NOK ohne MwSt., mit dem Steuersatz 25%"
**fr:** "Creer un produit appele Conseil Premium avec le prix 2500 NOK hors TVA"
**es:** "Crear un producto llamado Servicio Premium con precio 2500 NOK sin IVA, tasa de impuesto 25%"
**pt:** "Criar um produto chamado Consultoria Premium com preco 2500 NOK sem IVA, taxa de imposto 25%"

**Key fields:** name, number, price_excluding_vat, vat_percentage
**Gotcha:** VAT rate MUST be extracted -- hardcoding 0% or 25% will fail on non-standard rates

#### 8. CREATE_INVOICE

**nb:** "Lag faktura til kunde Nordfjord AS: 2 stk Konsulenttjeneste til 1500 kr"
**nb (multi-line):** "Lag faktura til kunde Nordfjord AS: 2 stk Konsulenttjeneste til 1500 kr og 1 stk Reise til 500 kr"
**nb:** "Opprett en faktura til Fjord AS for 5 stk Produkt A til 200 kr"
**en:** "Create an invoice for new customer Acme AS for 10 hours consulting at 1200 NOK per hour"
**de:** "Erstellen Sie eine Rechnung fuer Kunden Gruenfeld GmbH: 3 Stueck Beratung zu 1500 NOK"
**fr:** "Creer une facture pour le client Colline SARL pour 2 heures de conseil a 1500 NOK"
**es:** "Crear una factura para el cliente Empresa SA por 2 unidades de Producto X a 500 NOK cada una"
**pt:** "Criar uma fatura para o cliente Silva Ltda por 5 unidades de Produto A a 200 NOK cada"

**Key fields:** customer_name, lines[{description, quantity, unit_price}]
**Patterns:**
- "N stk X til Y kr" (nb: N pcs X at Y kr)
- "N hours X at Y NOK/hr" (en)
- "N unidades de X a Y NOK" (es)
- Multiple lines separated by "og" / "and" / "und" / "et" / "y" / "e"

#### 9. CREATE_DEPARTMENT

**nb:** "Opprett avdeling Salg med nummer 99"
**nn:** "Opprett ein ny avdeling som heiter Marknadsfoering"
**en:** "Create a department called Engineering with number 42"
**en (batch):** "Create three departments in Tripletex: Utvikling, Innkjop, and Salg."
**de:** "Erstellen Sie eine Abteilung namens Vertrieb"
**fr:** "Creer un departement appele Marketing"
**es:** "Crear un departamento llamado Marketing con numero 42"
**pt:** "Criar um departamento chamado Engenharia com numero 42"

**Key fields:** name, department_number
**Gotcha:** Batch operations! "Create three departments: X, Y, and Z"

#### 10. CREATE_PROJECT

**nb:** "Opprett prosjekt Nettside Redesign med startdato 2026-04-01"
**nn:** "Lag eit prosjekt Webside for kunde Digital AS med fast pris 50000 kr"
**en:** "Create a project called Website Redesign"
**de:** "Erstellen Sie ein Projekt namens Datenanalyse"
**fr:** "Creer un projet appele Refonte du Site Web, debut le 01/04/2026"
**es:** "Crear un proyecto llamado Rediseno Web, inicio el 01/04/2026"
**pt:** "Criar um projeto chamado Website Redesign para o cliente ABC Corp"

**Key fields:** name, start_date, end_date, customer_name, is_fixed_price, fixed_price

### Tier 2 -- Multi-step workflows (x2 multiplier)

#### 11. INVOICE_EXISTING_CUSTOMER

**nb:** "Opprett faktura til eksisterende kunde Nordic Tech AS for 3 timer konsulentarbeid til 1200 kr"
**en:** "Invoice customer Acme AS for 5 units of Widget at 500 NOK each"
**de:** "Erstellen Sie eine Rechnung fuer den bestehenden Kunden Gruenfeld GmbH ueber 5 Stueck Widget zu 500 NOK"
**fr:** "Facturer le client existant Colline SARL pour 3 heures de conseil a 1200 NOK"
**es:** "Crear factura para cliente existente Nordic Tech AS, 1 unidad de Servicio Premium a 3000 NOK"
**pt:** "Criar fatura para o cliente existente Silva Ltda, 5 unidades de Produto A a 200 NOK"

**Key fields:** customer_identifier, lines[{description, quantity, unit_price}]
**Difference from CREATE_INVOICE:** References an existing customer (by name, not creating new)

#### 12. REGISTER_PAYMENT

**nb:** "Registrer innbetaling pa faktura 10042 med belop 15000 kr, dato 15.03.2026"
**nb:** "Registrer innbetaling 25000 kr pa faktura nummer 10099, dato 2026-03-20"
**en:** "Register payment of 5000 NOK on invoice 20055"
**de:** "Registrieren Sie eine Zahlung von 5000 NOK fuer Rechnung 20055"
**fr:** "Enregistrer un paiement de 5000 NOK sur la facture 20055"
**es:** "Registrar pago de 5000 NOK en factura 20055"
**pt:** "Registrar pagamento de 5000 NOK na fatura 20055"

**Key fields:** invoice_identifier (number), amount, payment_date

#### 13. CREATE_CREDIT_NOTE

**nb:** "Opprett kreditnota for faktura 10055"
**en:** "Create a credit note for invoice 10055"
**de:** "Erstellen Sie eine Gutschrift fuer Rechnung 10055"
**fr:** "Creer un avoir pour la facture 10055"
**es:** "Crear una nota de credito para la factura 10055"
**pt:** "Criar uma nota de credito para a fatura 10055"

**Key fields:** invoice_identifier (number)

#### 14. INVOICE_WITH_PAYMENT

**nb:** "Opprett en faktura til Fjord AS for 5 stk Produkt A til 200 kr og registrer betaling"
**nb:** "Opprett faktura til kunde Fjord AS for 2 stk Tjeneste til 3000 kr, betalt i sin helhet"
**nb (narrative):** "Kunden Brattli AS (org.nr 909268265) har en utestaende faktura pa 31300 kr eksklusiv MVA for 'Konsulenttimer'. Registrer innbetalingen."
**en:** "Create an invoice for Acme Corp for 3 hours consulting at 1500 NOK/hr, already paid in full"
**de:** "Der Kunde Mueller GmbH hat eine unbezahlte Rechnung ueber 5000 NOK fuer Beratung. Zahlung registrieren."
**fr:** "Le client Colline SARL (no org. 850491941) a une facture impayee de 10550 NOK hors TVA pour 'Heures de conseil'. Enregistrer le paiement."
**es:** "El cliente Empresa SA (no org. 123456789) tiene una factura impaga de 10000 NOK sin IVA por 'Horas de consultoria'. Registrar el pago."
**pt:** "O cliente Silva Ltda (no org. 123456789) tem uma fatura em aberto de 8000 NOK sem IVA por 'Horas de consultoria'. Registrar o pagamento."

**Key fields:** customer_name, organization_number, lines[{description, quantity, unit_price}], paid_amount
**CRITICAL GOTCHA:** This is the most misclassified task. The grader sends narrative prompts describing "unpaid invoice" + "register payment" which LOOKS like REGISTER_PAYMENT but is actually INVOICE_WITH_PAYMENT because the invoice doesn't exist yet in the system. Must create customer + invoice + register payment.

**Disambiguation signals:**
- Customer details (name, org number) present -> invoice doesn't exist yet -> INVOICE_WITH_PAYMENT
- "facture impayee" / "unbezahlte Rechnung" / "utestaende faktura" / "unpaid invoice" + customer details -> INVOICE_WITH_PAYMENT
- Invoice number present (e.g., "faktura 10042") -> invoice exists -> REGISTER_PAYMENT
- No invoice number + customer details + amount + "register payment" -> INVOICE_WITH_PAYMENT

#### 15. CREATE_TRAVEL_EXPENSE

**nb:** "Opprett reiseregning for ansatt Per Hansen, dagsreise fra Bergen til Oslo 19. mars 2026, formal: kundemoete"
**nn:** "Opprett reiserekning for tilsett Per Hansen, dagsreise fraa Bergen til Oslo 19. mars 2026, formaal: kundemoete"
**en:** "Create travel expense for employee John Smith, day trip from Oslo to Bergen on March 20 2026, purpose: client meeting"
**de:** "Erstellen Sie eine Reisekostenabrechnung fuer Mitarbeiter Hans Mueller, Tagesreise von Hamburg nach Berlin am 19. Maerz 2026"
**fr:** "Creer une note de frais pour l'employe Pierre Dupont, voyage d'un jour de Paris a Lyon le 19 mars 2026, objet: reunion client"
**es:** "Crear un gasto de viaje para el empleado Juan Garcia, viaje de un dia de Madrid a Barcelona el 19 de marzo de 2026"
**pt:** "Criar uma despesa de viagem para o funcionario Carlos Silva, viagem de um dia de Lisboa a Porto em 19 de marco de 2026"

**Key fields:** employee_identifier, departure_from, destination, departure_date, return_date, is_day_trip, purpose, title

#### 16. DELETE_TRAVEL_EXPENSE

**nb:** "Slett reiseregning for ansatt Per Hansen"
**nn:** "Slett reiserekning for tilsett Ola Nordmann"
**en:** "Delete travel expense for employee John Smith"
**de:** "Loeschen Sie die Reisekostenabrechnung fuer Mitarbeiter Hans Mueller"
**fr:** "Supprimer la note de frais de l'employe Pierre Dupont"
**es:** "Eliminar el gasto de viaje del empleado Juan Garcia"
**pt:** "Excluir a despesa de viagem do funcionario Carlos Silva"

**Key fields:** travel_expense_identifier or employee_identifier

#### 17. PROJECT_WITH_CUSTOMER

**nb:** "Opprett prosjekt Nettside og knytt til kunde Digital AS"
**nb:** "Lag eit prosjekt Webside for kunde Digital AS med fast pris 50000 kr"
**nn:** "Opprett prosjektet Analyse Sjobris knytt til kunden Sjobris AS (org.nr 883693329). Prosjektleiar er Steinar Berge (steinar@sjobris.no)"
**nn:** "Opprett prosjektet Analyse knytt til kunden Sjobris AS. Prosjektleiar er Steinar Berge."
**en:** "Create a project Website linked to customer Acme Corp"
**de:** "Erstellen Sie ein Projekt Datenanalyse fuer den Kunden Gruenfeld GmbH"
**fr:** "Creer un projet Refonte du Site Web pour le client Colline SARL"
**es:** "Crear un proyecto Rediseno Web para el cliente Empresa SA"
**pt:** "Criar um projeto chamado Website Redesign para o cliente ABC Corp"

**Key fields:** project_name, customer_identifier, organization_number, project_manager_name, project_manager_email, start_date, is_fixed_price, fixed_price

**Patterns to note:**
- "knytt til kunden X" (nn: linked to customer X)
- "og knytt til kunde X" (and link to customer X)
- "for kunde X" (for customer X)
- "Prosjektleiar er X (email)" (Project manager is X)
- Customer org number in parentheses

#### 18. PROJECT_BILLING

**nb:** "Fakturer prosjekt Alpha for 10 timer konsulentarbeid til 1500 kr"
**en:** "Invoice project Beta for consulting services"
**de:** "Rechnung fuer Projekt Alpha erstellen: 10 Stunden Beratung zu 1500 NOK"
**fr:** "Facturer le projet Alpha pour 10 heures de conseil a 1500 NOK"
**es:** "Facturar el proyecto Alpha por 10 horas de consultoria a 1500 NOK"
**pt:** "Faturar o projeto Alpha por 10 horas de consultoria a 1500 NOK"

**Key fields:** project_identifier, lines[{description, quantity, unit_price}]

#### 19. CREATE_CONTACT

**nb:** "Opprett kontaktperson for kunde Nordic Tech AS: Per Hansen, per@nordic.no"
**nb:** "Opprett kontaktperson Anna Stress for kunde Stresstest Corp AS"
**en:** "Add a contact person Jane Doe for customer Nordic Tech AS, email jane@nordic.no"
**de:** "Erstellen Sie einen Kontakt Max Mustermann fuer den Kunden Gruenfeld GmbH, E-Mail max@gruenfeld.de"
**fr:** "Creer un contact Jean Dupont pour le client Acme AS, email jean@acme.fr"
**es:** "Crear un contacto Juan Garcia para el cliente Empresa SA, email juan@empresa.es"
**pt:** "Criar um contato Carlos Silva para o cliente Silva Ltda, email carlos@silva.pt"

**Key fields:** first_name, last_name, customer_identifier, email, phone

#### 20. FIND_CUSTOMER

**nb:** "Finn kunde med org.nr 912345678"
**en:** "Find customer with organization number 912345678"
**de:** "Finden Sie den Kunden mit Organisationsnummer 912345678"
**fr:** "Trouver le client avec le numero d'organisation 912345678"
**es:** "Buscar el cliente con numero de organizacion 912345678"
**pt:** "Encontrar o cliente com numero de organizacao 912345678"

**Key fields:** search_query, search_field (name, organization_number, email)

#### 21. UPDATE_PROJECT

**nb:** "Oppdater prosjekt Alpha med ny sluttdato 2026-12-31"
**en:** "Update project Beta description to Phase 2"
**de:** "Aktualisieren Sie Projekt Alpha mit neuem Enddatum 2026-12-31"
**fr:** "Modifier le projet Alpha avec nouvelle date de fin 2026-12-31"
**es:** "Actualizar el proyecto Alpha con nueva fecha de fin 2026-12-31"
**pt:** "Atualizar o projeto Alpha com nova data de termino 2026-12-31"

**Key fields:** project_identifier, new_name, new_description, new_start_date, new_end_date, is_closed

#### 22. DELETE_PROJECT

**nb:** "Slett prosjekt Alpha"
**en:** "Delete project Beta"
**de:** "Loeschen Sie Projekt Alpha"
**fr:** "Supprimer le projet Alpha"
**es:** "Eliminar el proyecto Alpha"
**pt:** "Excluir o projeto Alpha"

**Key fields:** project_identifier

### Tier 3 -- Complex scenarios (x3 multiplier)

#### 23. BANK_RECONCILIATION

**nb:** "Bankavstemming for mars 2026"
**en:** "Perform bank reconciliation for March 2026"
**de:** "Bankasvtemming fuer Maerz 2026 durchfuehren"
**fr:** "Effectuer un rapprochement bancaire pour mars 2026"
**es:** "Realizar conciliacion bancaria para marzo 2026"
**pt:** "Realizar conciliacao bancaria para marco 2026"

**Key fields:** period_start, period_end, account_number, transactions (from file)
**Note:** Often comes with attached CSV file containing transactions

#### 24. ERROR_CORRECTION

**nb:** "Korriger feil i bilag 1234"
**en:** "Correct error in voucher 1234"
**de:** "Fehler in Beleg 1234 korrigieren"
**fr:** "Corriger l'erreur dans la piece comptable 1234"
**es:** "Corregir error en comprobante 1234"
**pt:** "Corrigir erro no comprovante 1234"

**Key fields:** voucher_identifier, correction_description

#### 25. YEAR_END_CLOSING

**nb:** "Aarsavslutning 2025"
**en:** "Year-end closing for 2025"
**de:** "Jahresabschluss 2025"
**fr:** "Cloture annuelle 2025"
**es:** "Cierre anual 2025"
**pt:** "Encerramento anual 2025"

**Key fields:** year

#### 26. ENABLE_MODULE

**nb:** "Aktiver modul Reiseregning"
**en:** "Enable the travel expense module"
**de:** "Aktivieren Sie das Reisekostenmodul"
**fr:** "Activer le module note de frais"
**es:** "Activar el modulo de gastos de viaje"
**pt:** "Ativar o modulo de despesas de viagem"

**Key fields:** module_name

---

## Multi-Step Task Complexity

### How the grader structures compound tasks

**Pattern 1: Explicit multi-step ("and")**
```
Opprett en faktura til Fjord AS for 5 stk Produkt A til 200 kr og registrer betaling
```
Signal: "og registrer betaling" / "and register payment" / "und Zahlung registrieren"

**Pattern 2: Narrative with implicit steps**
```
Kunden Brattli AS (org.nr 909268265) har en utestaende faktura pa 31300 kr eksklusiv MVA
for "Konsulenttimer". Registrer innbetalingen.
```
Signal: Customer details + invoice details + "register payment" but no invoice number

**Pattern 3: State-based ("already paid")**
```
Create an invoice for Acme Corp for 3 hours consulting at 1500 NOK/hr, already paid in full
```
Signal: "already paid in full" / "betalt i sin helhet"

**Pattern 4: Customer + project compound**
```
Opprett prosjektet Analyse Sjobris knytt til kunden Sjobris AS (org.nr 883693329).
Prosjektleiar er Steinar Berge (steinar@sjobris.no)
```
Signal: "knytt til kunden" / "linked to customer" + customer details in project creation

**Pattern 5: Employee + role compound**
```
Opprett en ansatt med navn Ola Nordmann, ola@example.org. Han skal vaere kontoadministrator.
```
Signal: CREATE_EMPLOYEE but with "skal vaere kontoadministrator" appended

---

## Potential Gotchas

### 1. INVOICE_WITH_PAYMENT vs REGISTER_PAYMENT (CRITICAL)

**Problem:** The grader describes a customer with an "unpaid invoice" and asks to "register payment." This LOOKS like REGISTER_PAYMENT but the invoice doesn't exist in the system -- it must be created first.

**Rule:**
- Has invoice NUMBER (e.g., "faktura 10042") -> REGISTER_PAYMENT
- Has customer NAME + amount + "register payment" but NO invoice number -> INVOICE_WITH_PAYMENT

**Known failure:** Grader request #1 (French) was misclassified as REGISTER_PAYMENT, causing the agent to search for a non-existent invoice.

### 2. Org number used as invoice number

**Problem:** When the prompt contains an org number and asks to register payment, the agent may use the org number as the invoice number.

**Rule:** Org numbers (9 digits) are NOT invoice numbers. They're always prefixed with "org.nr" / "Organisationsnummer" / "no org." context.

### 3. Mixed-language dates

**Problem:** The grader has been observed using "4. May 1986" -- a Norwegian date structure ("4.") with an English month name ("May").

**Rule:** The date parser must handle all month names in all 7 languages, plus mixed formats.

### 4. Employee role inline with creation

**Problem:** "Opprett ansatt X... Han/Ho skal vaere/ha [role]" -- role assignment embedded in employee creation.

**Rule:** If CREATE_EMPLOYEE prompt also mentions a role, extract user_type field.

### 5. VAT rate variation

**Problem:** Grader sends different VAT rates (25%, 15%, 12%, 0%). Hardcoding any rate will fail.

**Rule:** Always extract vat_percentage from the prompt and look up the matching vatType in Tripletex.

### 6. Batch operations

**Problem:** "Create three departments: X, Y, and Z" -- single prompt, multiple entities.

**Rule:** Must detect batch and return array of classifications.

### 7. Norwegian characters in different encodings

**Problem:** Some grader prompts have been observed with:
- Full Unicode: "Sjobris", "Marknadsfoering", "foedt"
- ASCII-folded: "Sjobris", "Marknadsfoering", "fodt"
- Mixed: "aerz" vs "arz"

**Rule:** Classifier must handle both forms.

### 8. "eksisterende" (existing) customer disambiguation

**Problem:** "Opprett faktura til eksisterende kunde Nordic Tech AS" explicitly says existing customer -> INVOICE_EXISTING_CUSTOMER. But most grader prompts don't say "eksisterende" -- they just name the customer, which could be new or existing.

**Rule:** Default to CREATE_INVOICE (which creates customer if needed) unless explicitly "existing" / "eksisterende" / "bestehenden".

### 9. Empty prompts

**Problem:** Grader occasionally sends empty prompts (health checks?).

**Rule:** Must handle gracefully and return quickly.

### 10. Truncated prompt previews

**Problem:** Log entries truncate at ~120 characters. Some prompts are much longer, and the truncated suffix may contain critical data.

**Common truncated suffixes:**
- "...steinar@sjobris.no)" (email at end of project+customer prompt)
- "...astrid.strand@example.org" (email at end of employee prompt)
- "...Registrer innbetalingen." (payment instruction at end of invoice prompt)
- "...3015 Drammen" (address at end of customer prompt)
- "...Steuersatz 25%" (VAT rate at end of product prompt)

### 11. Price format: "eksklusiv MVA" vs amount already excluding VAT

**Problem:** "31300 kr eksklusiv MVA" means the amount IS the pre-tax amount. "10550 NOK hors TVA" same. The agent must NOT try to remove VAT from this amount.

**Rule:** When "eks. mva" / "hors TVA" / "ohne MwSt." / "excluding VAT" is present, the stated amount IS the pre-tax price.

### 12. "startDate" required field

**Problem:** Tripletex API requires startDate for employee creation. If not in prompt, must default to today.

**Rule:** Always include startDate field in employee POST, defaulting to today if not specified.

---

## Coverage Gaps

### Task types NOT yet seen from grader

The following have been tested by us but never confirmed from the actual grader:

| Task Type | Tested? | Risk Level |
|-----------|---------|------------|
| CREATE_EMPLOYEE | Confirmed from grader | LOW |
| CREATE_CUSTOMER | Confirmed from grader | LOW |
| CREATE_PRODUCT | Confirmed from grader | LOW |
| CREATE_DEPARTMENT | Confirmed from grader | LOW |
| CREATE_INVOICE | Confirmed from grader | LOW |
| PROJECT_WITH_CUSTOMER | Confirmed from grader | LOW |
| INVOICE_WITH_PAYMENT | Confirmed from grader | LOW |
| UPDATE_EMPLOYEE | Our tests only | MEDIUM |
| DELETE_EMPLOYEE | Our tests only | MEDIUM |
| SET_EMPLOYEE_ROLES | Our tests only | MEDIUM |
| UPDATE_CUSTOMER | Our tests only | MEDIUM |
| INVOICE_EXISTING_CUSTOMER | Our tests only | MEDIUM |
| REGISTER_PAYMENT | Our tests only | MEDIUM |
| CREATE_CREDIT_NOTE | Our tests only | MEDIUM |
| CREATE_TRAVEL_EXPENSE | Our tests only | MEDIUM |
| DELETE_TRAVEL_EXPENSE | Our tests only | MEDIUM |
| PROJECT_BILLING | Our tests only | MEDIUM |
| CREATE_CONTACT | Our tests only | MEDIUM |
| FIND_CUSTOMER | Our tests only | MEDIUM |
| UPDATE_PROJECT | Our tests only | MEDIUM |
| DELETE_PROJECT | Our tests only | MEDIUM |
| BANK_RECONCILIATION | Our tests only | HIGH |
| ERROR_CORRECTION | Our tests only | HIGH |
| YEAR_END_CLOSING | Our tests only | HIGH |
| ENABLE_MODULE | Our tests only | HIGH |

### Languages NOT yet seen from grader

- Spanish (es): zero confirmed grader requests
- Portuguese (pt): zero confirmed grader requests

Both languages are tested via our own test suite but their actual grader prompt patterns are projected based on the patterns of confirmed languages.

### Data sets

With 8 data sets per task, we expect variation in:
- Company names (Norwegian, German, French, generic English)
- Personal names (per language)
- Org numbers (different 9-digit numbers)
- Addresses (different Norwegian addresses)
- Amounts (different price points)
- Dates (different months, years)
- Product/service descriptions
- Department/project names

The grader likely has 8 fixed data sets that rotate across the 7 languages, giving 56 total variants per task type.
