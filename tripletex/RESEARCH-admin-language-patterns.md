# System Admin + Multi-Language Patterns — Tripletex API Research

**Date:** 2026-03-21
**Purpose:** Document system admin persona capabilities + comprehensive 7-language terminology for classifier improvement.

---

## 1. System Admin Persona

### Who is the Systemansvarlig?

The **Systemansvarlig** (System Administrator) is a Tripletex user role responsible for:
- Enabling/disabling company modules (Prosjekt, Faktura, Avdeling, etc.)
- Configuring company-wide settings (Altinn integration, bank accounts, currency)
- Managing user access and session tokens
- Setting up bank account prerequisites (required before invoicing works)
- Year-end closing, reconciliation oversight

### Admin Tasks in Our Task Types

| Task Type | Admin Relevance | Tier |
|-----------|----------------|------|
| `enable_module` | Core admin task — toggle company modules on/off | T3 (×3) |
| `bank_reconciliation` | Financial admin — reconcile bank transactions | T3 (×3) |
| `year_end_closing` | Annual admin procedure | T3 (×3) |
| `error_correction` | Fix ledger errors — admin-level access | T3 (×3) |
| `set_employee_roles` | Access management — set user types | T1 (×1) |
| `create_dimension_voucher` | Custom accounting dimensions — power user/admin | T3 (×3) |

### Admin-Specific Prompt Patterns

Norwegian:
- "Aktiver modulen Prosjekt" / "Slå på modul Faktura"
- "Vis alle tilgjengelige moduler"
- "Konfigurer bankkonto for konto 1920"
- "Sett opp Altinn-integrasjon"
- "Sjekk hvilke moduler som er aktive"

English:
- "Enable the Project module"
- "Show all available modules"
- "Configure bank account for account 1920"
- "Set up Altinn integration"

German:
- "Aktivieren Sie das Projektmodul"
- "Zeigen Sie alle verfügbaren Module an"
- "Bankkonto für Konto 1920 konfigurieren"

---

## 2. Admin API Endpoints

### 2.1 Company Modules — GET /company/modules

**This endpoint returns all module toggles as a flat boolean object:**

```json
{
  "ocr": false,
  "autoPayOcr": false,
  "remit": false,
  "agro": false,
  "mamut": false,
  "approveVoucher": false,
  "moduleprojecteconomy": true,
  "moduleemployee": true,
  "moduleContact": true,
  "modulecustomer": true,
  "modulenrf": false,
  "moduleelectro": false,
  "moduleRackbeat": false,
  "moduleOrderOut": false,
  "moduledepartment": true,
  "moduleprojectcategory": true,
  "moduleinvoice": true,
  "moduleCurrency": true,
  "moduleProjectBudget": true,
  "moduleProduct": true,
  "moduleQuantityHandling": false,
  "completeMonthlyHourLists": false,
  "moduleDepartmentAccounting": false,
  "moduleWageProjectAccounting": true,
  "moduleProjectAccounting": true,
  "moduleProductAccounting": false,
  "moduleVacationBalance": true,
  "moduleHolydayPlan": true,
  "moduleAccountantConnectClient": false,
  "moduleMultipleLedgers": false,
  "moduleFixedAssetRegister": false,
  "moduleDigitalSignature": false,
  "moduleLogistics": false,
  "moduleLogisticsLight": false,
  "moduleproject": true
}
```

**Currently enabled modules:** moduleprojecteconomy, moduleemployee, moduleContact, modulecustomer, moduledepartment, moduleprojectcategory, moduleinvoice, moduleCurrency, moduleProjectBudget, moduleProduct, moduleWageProjectAccounting, moduleProjectAccounting, moduleVacationBalance, moduleHolydayPlan, moduleproject

**Currently disabled modules (can be enabled):** ocr, autoPayOcr, remit, agro, mamut, approveVoucher, modulenrf, moduleelectro, moduleRackbeat, moduleOrderOut, moduleQuantityHandling, completeMonthlyHourLists, moduleDepartmentAccounting, moduleProductAccounting, moduleAccountantConnectClient, moduleMultipleLedgers, moduleFixedAssetRegister, moduleDigitalSignature, moduleLogistics, moduleLogisticsLight

### Module Name Mapping (API key → Human-readable)

| API Key | Norwegian | English |
|---------|-----------|---------|
| moduleproject | Prosjekt | Project |
| moduleinvoice | Faktura | Invoice |
| modulecustomer | Kunde | Customer |
| moduleemployee | Ansatt | Employee |
| moduledepartment | Avdeling | Department |
| moduleProduct | Produkt | Product |
| moduleCurrency | Valuta | Currency |
| moduleProjectBudget | Prosjektbudsjett | Project Budget |
| moduleprojecteconomy | Prosjektøkonomi | Project Economy |
| moduleprojectcategory | Prosjektkategori | Project Category |
| moduleProjectAccounting | Prosjektregnskap | Project Accounting |
| moduleWageProjectAccounting | Lønnsprosjektregnskap | Wage Project Accounting |
| moduleVacationBalance | Feriesaldo | Vacation Balance |
| moduleHolydayPlan | Ferieplan | Holiday Plan |
| moduleContact | Kontakt | Contact |
| moduleDepartmentAccounting | Avdelingsregnskap | Department Accounting |
| moduleProductAccounting | Produktregnskap | Product Accounting |
| moduleFixedAssetRegister | Anleggsregister | Fixed Asset Register |
| moduleDigitalSignature | Digital Signatur | Digital Signature |
| moduleLogistics | Logistikk | Logistics |
| moduleLogisticsLight | Logistikk Light | Logistics Light |
| moduleMultipleLedgers | Flere Regnskap | Multiple Ledgers |
| moduleAccountantConnectClient | Regnskapsfører Kobling | Accountant Connect |
| moduleOrderOut | Utgående Ordre | Outgoing Order |
| moduleQuantityHandling | Lagerstyring | Quantity Handling |
| approveVoucher | Godkjenn Bilag | Approve Voucher |
| ocr | OCR | OCR |
| autoPayOcr | AutoPay OCR | AutoPay OCR |
| remit | Remittering | Remittance |
| completeMonthlyHourLists | Månedlige Timelister | Monthly Hour Lists |

### 2.2 Altinn Settings — GET /company/settings/altinn

```json
{"altInnId": 0, "altInnPassword": ""}
```
Empty in sandbox — would contain the company's Altinn ID for tax/government reporting.

### 2.3 Event Types — GET /event

All available event types in the system:
- invoice.charged, employee.create, employee.update, employee.delete
- supplier.create, supplier.update, supplier.delete
- product.create, product.update, product.delete
- order.create, order.update, order.delete
- customer.create, customer.update, customer.delete
- contact.create, contact.update, contact.delete
- account.create, account.update, account.delete
- voucher.create, voucher.update, voucher.delete
- project.create, project.update, project.delete
- notification.sent, voucherstatus.ready
- vatdeliverystatus.create/update/delete, vatpaymentstatus.update
- archiverelation.create/update/delete (BETA)
- expiredcompany.deleted, tripletexcustomer.update

### 2.4 Bank Accounts — GET /ledger/account?isBankAccount=true

Two bank accounts found:
1. **Account 1920 "Bankinnskudd"** — Main bank account
   - bankAccountNumber: "12345678903"
   - requireReconciliation: true
   - isBankAccount: true, isInvoiceAccount: true
   - Has postings (isPostingsExist: true)

2. **Account 1950 "Bankinnskudd for skattetrekk"** — Tax deduction account
   - bankAccountNumber: "" (not configured)
   - requireReconciliation: false
   - isBankAccount: true, isInvoiceAccount: false

**Critical insight:** Account 1920 must have a valid bankAccountNumber before invoicing works. This is a common admin setup task.

### 2.5 Session / Auth — GET /token/session/>whoAmI

```json
{
  "employeeId": 18491802,
  "companyId": 108167433,
  "language": "no",
  "loggedInWithConnect": false,
  "employeeIsProxy": false
}
```

---

## 3. Module Management

### How Modules Work

Modules are company-level feature toggles. Enabling a module unlocks specific API endpoints and functionality.

### Enable/Disable via API

**Endpoint:** `PUT /company/modules` with JSON body containing the module flags to change.

Example to enable the Project module:
```json
PUT /company/modules
{"moduleproject": true}
```

### Module Dependencies

Some modules depend on others:
- moduleProjectAccounting requires moduleproject
- moduleProjectBudget requires moduleproject
- moduleDepartmentAccounting requires moduledepartment
- moduleProductAccounting requires moduleProduct
- moduleWageProjectAccounting requires moduleemployee

### Admin Prompt → API Call Mapping

| Prompt Pattern | API Call |
|---------------|----------|
| "Aktiver modul X" | PUT /company/modules {moduleX: true} |
| "Deaktiver modul X" | PUT /company/modules {moduleX: false} |
| "Vis moduler" / "List modules" | GET /company/modules |
| "Konfigurer bankkonto" | GET + PUT /ledger/account |

---

## 4. Entity Terminology Matrix (All 7 Languages)

### Core Entities

| Entity | nb (Bokmål) | nn (Nynorsk) | en (English) | de (German) | fr (French) | es (Spanish) | pt (Portuguese) |
|--------|-------------|--------------|--------------|-------------|-------------|--------------|-----------------|
| Customer | kunde | kunde | customer | Kunde | client | cliente | cliente |
| Employee | ansatt | tilsett | employee | Mitarbeiter | employé | empleado | funcionário / empregado |
| Product | produkt | produkt | product | Produkt | produit | producto | produto |
| Department | avdeling | avdeling | department | Abteilung | département | departamento | departamento |
| Project | prosjekt | prosjekt | project | Projekt | projet | proyecto | projeto |
| Supplier | leverandør | leverandør | supplier | Lieferant | fournisseur | proveedor | fornecedor |
| Invoice | faktura | faktura | invoice | Rechnung | facture | factura | fatura |
| Order | ordre | ordre | order | Auftrag/Bestellung | commande | pedido/orden | pedido/encomenda |
| Payment | betaling / innbetaling | betaling | payment | Zahlung | paiement | pago | pagamento |
| Credit Note | kreditnota | kreditnota | credit note | Gutschrift | avoir / note de crédit | nota de crédito | nota de crédito |
| Voucher | bilag | bilag | voucher | Beleg | pièce comptable / écriture | asiento / comprobante | lançamento / comprovante |
| Travel Expense | reiseregning | reiserekning | travel expense | Reisekostenabrechnung | note de frais | gasto de viaje | despesa de viagem |
| Salary/Payroll | lønn / lønnskjøring | løn / lønskøyring | salary / payroll | Gehalt / Gehaltsabrechnung | salaire / paie | salario / nómina | salário / folha de pagamento |
| Bank Reconciliation | bankavstemming | bankavstemming | bank reconciliation | Bankabgleich / Kontoabstimmung | rapprochement bancaire | conciliación bancaria | conciliação bancária |
| Year-End Closing | årsavslutning / årsoppgjør | årsavslutning | year-end closing | Jahresabschluss | clôture annuelle / clôture de l'exercice | cierre anual / cierre del ejercicio | encerramento anual |
| Module | modul | modul | module | Modul | module | módulo | módulo |
| Contact | kontaktperson | kontaktperson | contact (person) | Kontaktperson / Ansprechpartner | personne de contact | persona de contacto | pessoa de contato |
| Dimension | dimensjon | dimensjon | dimension | Dimension / Buchhaltungsdimension | dimension | dimensión | dimensão |
| Account | konto | konto | account | Konto | compte | cuenta | conta |
| Role | rolle | rolle | role | Rolle | rôle | rol | papel / função |
| Supplier Invoice | leverandørfaktura | leverandørfaktura | supplier invoice | Eingangsrechnung | facture fournisseur | factura de proveedor | fatura de fornecedor |
| Hours/Time Entry | timer / timeføring | timar / timeføring | hours / time entry | Stunden / Zeiterfassung | heures / saisie de temps | horas / registro de tiempo | horas / registro de horas |

### Financial/Accounting Terms

| Term | nb | nn | en | de | fr | es | pt |
|------|----|----|----|----|----|----|-----|
| VAT / MVA | merverdiavgift (MVA) | meirverdiavgift (MVA) | VAT | Mehrwertsteuer (MwSt) | TVA | IVA | IVA |
| Tax | skatt | skatt | tax | Steuer | impôt / taxe | impuesto | imposto |
| Debit | debet | debet | debit | Soll | débit | débito | débito |
| Credit | kredit | kredit | credit | Haben | crédit | crédito | crédito |
| Balance | saldo | saldo | balance | Saldo | solde | saldo | saldo |
| Ledger | regnskap / hovedbok | rekneskap / hovudbok | ledger | Hauptbuch | grand livre | libro mayor | razão geral |
| Posting | postering | postering | posting | Buchung | écriture | asiento | lançamento |
| Due date | forfallsdato | forfallsdato | due date | Fälligkeitsdatum | date d'échéance | fecha de vencimiento | data de vencimento |
| Amount | beløp | beløp | amount | Betrag | montant | importe / monto | valor / montante |
| Price | pris | pris | price | Preis | prix | precio | preço |
| Discount | rabatt | rabatt | discount | Rabatt | remise / rabais | descuento | desconto |
| Currency | valuta | valuta | currency | Währung | devise / monnaie | moneda / divisa | moeda |
| Interest | rente | rente | interest | Zinsen | intérêt | interés | juros |
| Org Number | organisasjonsnummer (org.nr) | organisasjonsnummer | organization number | Organisationsnummer | numéro d'organisation | número de organización | número da organização |

---

## 5. Verb/Action Matrix (All 7 Languages)

### Primary Actions

| Action | nb (Bokmål) | nn (Nynorsk) | en | de | fr | es | pt |
|--------|-------------|--------------|----|----|----|----|-----|
| Create | opprett / lag | opprett / lag | create / add | erstellen / anlegen | créer | crear | criar |
| Update | oppdater / endre | oppdater / endre | update / modify | aktualisieren / ändern | mettre à jour / modifier | actualizar / modificar | atualizar / modificar |
| Delete | slett / fjern | slett / fjern | delete / remove | löschen / entfernen | supprimer | eliminar / borrar | excluir / remover |
| Find/Search | finn / søk | finn / søk | find / search | finden / suchen | trouver / chercher | buscar / encontrar | buscar / encontrar / procurar |
| List/Show | vis / list | vis / list | list / show | anzeigen / auflisten | lister / afficher | listar / mostrar | listar / mostrar |
| Register | registrer | registrer | register | registrieren | enregistrer | registrar | registrar |
| Enable | aktiver / slå på | aktiver / slå på | enable / activate | aktivieren / einschalten | activer | activar | ativar |
| Disable | deaktiver / slå av | deaktiver / slå av | disable / deactivate | deaktivieren / ausschalten | désactiver | desactivar | desativar |
| Close | avslutt / lukk | avslutt / lukk | close | schließen / abschließen | clôturer / fermer | cerrar | fechar / encerrar |
| Correct | korriger / rett | korriger / rett | correct / fix | korrigieren / berichtigen | corriger | corregir | corrigir |
| Reverse | reverser / tilbakefør | reverser / tilbakefør | reverse / undo | stornieren / rückbuchen | annuler / contrepasser | revertir / anular | reverter / estornar |
| Pay | betal | betal | pay | bezahlen / zahlen | payer | pagar | pagar |
| Invoice (verb) | fakturer | fakturer | invoice / bill | fakturieren / in Rechnung stellen | facturer | facturar | faturar |
| Log/Record | logg / før / registrer | logg / før / registrer | log / record | erfassen / eintragen | enregistrer / saisir | registrar / anotar | registrar / lançar |
| Reconcile | avstem | avstem | reconcile | abgleichen / abstimmen | rapprocher | conciliar | conciliar |
| Run (payroll) | kjør | køyr | run / execute | ausführen / durchführen | exécuter | ejecutar | executar / processar |
| Configure | konfigurer / sett opp | konfigurer / sett opp | configure / set up | konfigurieren / einrichten | configurer | configurar | configurar |
| Send | send | send | send | senden / schicken | envoyer | enviar | enviar |

### Prepositions & Connectors

| Concept | nb | nn | en | de | fr | es | pt |
|---------|----|----|----|----|----|----|-----|
| for / to | til / for | til / for | for / to | für / an | pour / à | para / a | para / a |
| with | med | med | with | mit | avec | con | com |
| named / called | som heter / med navn | som heiter / med namn | named / called | namens / mit dem Namen | nommé / appelé | llamado / con nombre | chamado / com nome |
| new | ny / nytt | ny / nytt | new | neu / neue | nouveau / nouvelle | nuevo / nueva | novo / nova |
| existing | eksisterende | eksisterande | existing | bestehend / vorhandene | existant | existente | existente |
| from...to | fra...til | frå...til | from...to | von...bis | de...à | de...a / desde...hasta | de...a / desde...até |

---

## 6. Example Prompts per Language (3-5 Each)

### Norwegian Bokmål (nb)
1. "Opprett en ny kunde Fjord Konsult AS med org.nr 987654321"
2. "Lag faktura til Hansen Bygg AS for 5 timer konsulentarbeid à 1200 kr"
3. "Registrer innbetaling på faktura 10042 med beløp 15000 kr"
4. "Opprett reiseregning for ansatt Per Hansen, dagsreise Bergen–Oslo"
5. "Aktiver modulen Prosjektregnskap"
6. "Slett leverandør Maskin AS"
7. "Kjør lønn for ansatt Kari Nordmann, grunnlønn 45000 kr"

### Norwegian Nynorsk (nn)
1. "Opprett ein ny kunde Fjord Konsult AS med org.nr 987654321"
2. "Lag faktura til Hansen Bygg AS for 5 timar konsulentarbeid à 1200 kr"
3. "Registrer innbetaling på faktura 10042 med beløp 15000 kr"
4. "Opprett reiserekning for tilsett Per Hansen, dagsreise Bergen–Oslo"
5. "Aktiver modulen Prosjektrekneskap"

### English (en)
1. "Create a new customer named Nordic Solutions Ltd with org number 123456789"
2. "Create an invoice for Acme Corp: 10 hours consulting at 1200 NOK each"
3. "Register a payment of 15000 NOK on invoice 10042"
4. "Create a travel expense for employee John Smith, day trip Oslo to Bergen"
5. "Enable the Project Accounting module"
6. "Delete supplier TechParts Inc"
7. "Run payroll for employee Jane Doe, base salary 52000 NOK"

### German (de)
1. "Erstellen Sie einen neuen Kunden Schmidt GmbH mit Organisationsnummer 123456789"
2. "Erstellen Sie eine Rechnung für Müller AG: 5 Stunden Beratung zu je 1500 NOK"
3. "Registrieren Sie eine Zahlung von 15000 NOK auf Rechnung 10042"
4. "Erstellen Sie eine Reisekostenabrechnung für Mitarbeiter Hans Müller"
5. "Aktivieren Sie das Projektbuchhaltungsmodul"
6. "Registrieren Sie den Lieferanten Technik GmbH mit Org.Nr. 456789123"
7. "Führen Sie die Gehaltsabrechnung für Mitarbeiter Anna Schmidt durch, Grundgehalt 48000 NOK"

### French (fr)
1. "Créer un nouveau client Dupont SA avec le numéro d'organisation 987654321"
2. "Créer une facture pour le client Martin SARL: 8 heures de conseil à 1100 NOK"
3. "Enregistrer un paiement de 15000 NOK sur la facture 10042"
4. "Créer une note de frais pour l'employé Pierre Dupont, voyage aller-retour Paris-Lyon"
5. "Activer le module de comptabilité de projet"
6. "Enregistrer le fournisseur Composants FR avec org. 789123456"
7. "Exécutez la paie pour l'employé Marie Dupont, salaire de base 50000 NOK"

### Spanish (es)
1. "Crear un nuevo cliente García SL con número de organización 123456789"
2. "Crear una factura para Empresa SA: 3 sesiones de formación a 2500 NOK cada una"
3. "Registrar un pago de 15000 NOK en la factura 10042"
4. "Crear un gasto de viaje para el empleado Carlos García"
5. "Activar el módulo de contabilidad de proyectos"
6. "Eliminar proveedor Repuestos SL"
7. "Ejecutar nómina para empleado Ana Martínez, salario base 46000 NOK"

### Portuguese (pt)
1. "Criar um novo cliente Empresa Lda com número de organização 987654321"
2. "Criar uma fatura para o cliente Silva & Cia: 4 horas de consultoria a 1300 NOK"
3. "Registrar um pagamento de 15000 NOK na fatura 10042"
4. "Criar uma despesa de viagem para o funcionário João Silva"
5. "Ativar o módulo de contabilidade de projetos"
6. "Excluir fornecedor Peças Ltda"
7. "Processar folha de pagamento para funcionário Maria Silva, salário base 47000 NOK"

---

## 7. ASCII Folding Rules

### Norwegian (nb/nn)
| Original | Folded | Example |
|----------|--------|---------|
| å | a | årsavslutning → arsavslutning |
| ø | o | lønn → lonn, kjør → kjor |
| æ | ae | ære → aere |
| Å | A | Årsoppgjør → Arsoppgjor |
| Ø | O | Ødegaard → Odegaard |
| Æ | AE | Ærlig → AErlig |

**Common folded variants to match:**
- leverandør → leverandor
- lønnskjøring → lonnskjoring
- årsavslutning → arsavslutning, aarsavslutning
- årsoppgjør → arsoppgjor, aarsoppgjor
- slå på → slaa paa
- reiseregning → no folding needed
- bankavstemming → no folding needed
- førstegang → forstegang

### German (de)
| Original | Folded | Example |
|----------|--------|---------|
| ä | ae | ändern → aendern |
| ö | oe | löschen → loeschen |
| ü | ue | Müller → Mueller |
| ß | ss | schließen → schliessen |
| Ä | AE / Ae | Änderung → Aenderung |
| Ö | OE / Oe | Österreich → Oesterreich |
| Ü | UE / Ue | Übersicht → Uebersicht |

**Common folded variants:**
- löschen → loeschen
- ändern → aendern
- Gehaltsabrechnung → no folding needed
- Eingangsrechnung → no folding needed
- Reisekostenabrechnung → no folding needed
- Buchhaltungsdimension → no folding needed

### French (fr)
| Original | Folded | Example |
|----------|--------|---------|
| é | e | créer → creer |
| è | e | employé → employe (already é) |
| ê | e | clôture → cloture (ô→o) |
| ë | e | Noël → Noel |
| à | a | déjà → deja |
| â | a | clôture → cloture |
| ô | o | clôture → cloture |
| ù | u | où → ou |
| û | u | dû → du |
| ç | c | reçu → recu |
| î | i | connaître → connaitre |
| ï | i | naïf → naif |

**Common folded variants:**
- créer → creer
- département → departement
- clôture → cloture
- pièce → piece
- employé → employe
- écriture → ecriture
- facture → no folding needed

### Portuguese (pt)
| Original | Folded | Example |
|----------|--------|---------|
| ã | a | dimensão → dimensao |
| õ | o | ações → acoes |
| á | a | salário → salario |
| é | e | crédito → credito |
| í | i | funcionário → funcionario |
| ó | o | negócio → negocio |
| ú | u | conteúdo → conteudo |
| â | a | câmbio → cambio |
| ê | e | você → voce |
| ô | o | propôs → propos |
| ç | c | lançamento → lancamento |

**Common folded variants:**
- funcionário → funcionario
- dimensão → dimensao
- lançamento → lancamento
- conciliação → conciliacao
- fatura → no folding needed

### Spanish (es)
| Original | Folded | Example |
|----------|--------|---------|
| ñ | n | nómina → nomina (also ó→o) |
| á | a | crédito → credito |
| é | e | también → tambien |
| í | i | conciliación → conciliacion |
| ó | o | nómina → nomina |
| ú | u | facturación → facturacion |
| ü | u | bilingüe → bilingue |

**Common folded variants:**
- nómina → nomina
- conciliación → conciliacion
- dimensión → dimension
- facturación → facturacion
- módulo → modulo

---

## 8. Gap Analysis for Classifier

### Current Coverage (from `_KEYWORD_MAP` in main.py)

**Well-covered (all 7 languages):**
- CREATE/UPDATE/DELETE employee ✅
- CREATE/UPDATE/DELETE customer ✅
- CREATE/UPDATE/DELETE product ✅ (recently added)
- CREATE/UPDATE/DELETE project ✅
- CREATE/UPDATE department ✅
- CREATE invoice (all variants) ✅
- CREATE supplier / supplier invoice ✅
- Travel expense ✅
- Credit note ✅
- Register payment ✅
- Bank reconciliation ✅
- Year-end closing ✅
- Enable module ✅
- Run payroll ✅
- Reverse payment ✅
- Create dimension voucher ✅
- Log hours ✅
- Error correction ✅

### Gaps and Weaknesses

#### Gap 1: DELETE department / DELETE supplier — Missing Multi-Language Patterns
Current patterns in `_KEYWORD_MAP` don't list `delete_department` or `delete_supplier` explicitly. They may fall through to UNKNOWN.

**Missing regex patterns needed:**
```
DELETE_DEPARTMENT: (slett|fjern|delete|remove|löschen|supprimer|eliminar|excluir).*(avdeling|department|Abteilung|département|departamento)
DELETE_SUPPLIER: (slett|fjern|delete|remove|löschen|supprimer|eliminar|excluir).*(leverandør|supplier|Lieferant|fournisseur|proveedor|fornecedor)
```

#### Gap 2: FIND supplier — Weak Patterns
`FIND_SUPPLIER` is listed in task_types but the keyword map patterns may not cover all languages.

**Needed:**
```
FIND_SUPPLIER: (finn|find|søk|search|suchen|chercher|buscar|procurar).*(leverandør|supplier|Lieferant|fournisseur|proveedor|fornecedor)
```

#### Gap 3: UPDATE supplier — Weak Patterns
```
UPDATE_SUPPLIER: (oppdater|endre|update|modify|aktualisieren|ändern|modifier|actualizar|atualizar).*(leverandør|supplier|Lieferant|fournisseur|proveedor|fornecedor)
```

#### Gap 4: UPDATE contact — Limited Language Coverage
Current regex only covers a few languages.

#### Gap 5: ASCII-Folded Input Not Handled
If a user types "loschen" (instead of "löschen") or "creer" (instead of "créer"), the classifier may fail. The `_KEYWORD_MAP` does handle some Norwegian folding (ø→o, å→a) but not systematically for all languages.

**Key folded forms to add to patterns:**
- German: loeschen, aendern, Aenderung, Muller
- French: creer, departement, cloture, ecriture
- Portuguese: funcionario, dimensao, lancamento, conciliacao
- Spanish: nomina, conciliacion, modulo

#### Gap 6: Nynorsk "tilsett" Only Partially Covered
"tilsett" (Nynorsk for "ansatt") appears in CREATE/DELETE/UPDATE employee but is missing from some other patterns that reference employees (e.g., log hours, travel expense).

#### Gap 7: "kontaktperson" vs "kontakt" vs "contact"
Good disambiguation exists (using "kontaktperson" not bare "kontakt"), but German "Ansprechpartner" and French "personne de contact" are missing.

#### Gap 8: Module Enable — Missing Module Name Resolution
The `enable_module` pattern catches the intent but the executor needs to map human-readable module names to API keys:
- "Prosjekt" → moduleproject
- "Faktura" → moduleinvoice
- "Lagerstyring" → moduleQuantityHandling
- "Anleggsregister" → moduleFixedAssetRegister
- etc.

#### Gap 9: Invoice Verb Forms
Some languages use "facturer" (fr), "facturieren" (de), "faturar" (pt) as verbs meaning "to invoice." These may not be captured if the pattern requires "créer une facture" but the user says "facturer le client."

#### Gap 10: Compound German Words
German creates compounds like "Eingangsrechnung" (incoming invoice = supplier invoice), "Gehaltsabrechnung" (salary settlement = payroll), "Reisekostenabrechnung" (travel cost settlement = travel expense). These should be atomic matches, not split into verb+noun patterns.

---

## 9. Recommendations

### Immediate Fixes (Classifier Patterns)

1. **Add missing DELETE/FIND/UPDATE patterns for supplier and department** in all 7 languages
2. **Add ASCII-folded variants** for German, French, Portuguese, Spanish diacritics in the regex patterns
3. **Add German compound word patterns** as atomic matches: Eingangsrechnung, Gehaltsabrechnung, Reisekostenabrechnung, Kontoabstimmung, Jahresabschluss
4. **Add French compound phrases**: "note de frais", "rapprochement bancaire", "clôture annuelle", "personne de contact"
5. **Add Nynorsk "tilsett"** to all employee-related patterns

### Module Enable Improvements

6. **Build a module name mapping dict** in the executor:
   ```python
   MODULE_NAME_MAP = {
       "prosjekt": "moduleproject", "project": "moduleproject", "projekt": "moduleproject", "projet": "moduleproject",
       "faktura": "moduleinvoice", "invoice": "moduleinvoice", "rechnung": "moduleinvoice", "facture": "moduleinvoice",
       "kunde": "modulecustomer", "customer": "modulecustomer", "client": "modulecustomer", "kunde": "modulecustomer",
       # ... etc for all modules
   }
   ```

### LLM Classifier Improvements

7. **Add module-specific few-shot examples** to the Gemini system prompt
8. **Add ASCII-folding preprocessing** step before regex matching:
   ```python
   import unicodedata
   def ascii_fold(text):
       nfkd = unicodedata.normalize('NFKD', text)
       return ''.join(c for c in nfkd if not unicodedata.combining(c))
   ```
   Then match against both original and folded text.

### Admin Persona Support

9. **Add admin-specific prompt examples** to the LLM few-shot section
10. **Consider a LIST_MODULES task type** for "vis alle moduler" / "show all modules" — currently no matching task type exists for this read-only admin query

### Priority Order

| Priority | Fix | Impact | Effort |
|----------|-----|--------|--------|
| P0 | ASCII-folding preprocessing | Catches ALL unaccented input variants automatically | 5 lines |
| P0 | Missing DELETE/FIND/UPDATE patterns for supplier/department | Prevents UNKNOWN classification | ~10 regex lines |
| P1 | German compound words as atomic patterns | Major German language improvement | ~5 regex lines |
| P1 | Module name → API key mapping | Required for enable_module to work | ~30 lines dict |
| P2 | Nynorsk "tilsett" in all employee patterns | Nynorsk coverage | ~5 regex edits |
| P2 | French compound phrases | French language improvement | ~5 regex lines |
| P3 | Invoice verb forms (facturer, facturieren, faturar) | Edge case improvement | ~3 regex lines |
