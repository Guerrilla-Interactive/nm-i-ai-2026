# Accountant Workflows — Tripletex API Research

**Date:** 2026-03-21
**Sandbox:** `https://kkpqfuj-amager.tripletex.dev/v2`

---

## 1. User Persona: Regnskapsfører / Accountant

**Who they are:**
- Norwegian accountants ("regnskapsførere") managing day-to-day bookkeeping for small-to-medium companies
- Typically handle 5–50 client companies in Tripletex
- Work in Norwegian (bokmål/nynorsk), occasionally English, German, Swedish, Danish
- Deep knowledge of Norwegian Chart of Accounts (Norsk Standard Kontoplan, NS 4102)
- Think in terms of "bilag" (vouchers), "kontoer" (accounts), "mva" (VAT), "avstemming" (reconciliation)

**What they do daily:**
1. Import bank transactions → match to existing postings
2. Post incoming/outgoing invoices as vouchers
3. Reconcile bank account (1920) against ledger
4. Handle VAT (merverdiavgift) — compute, report, settle
5. Correct posting errors
6. End-of-month: close period, verify trial balance
7. End-of-year: closing entries (årsavslutning), equity transfer

**How they phrase requests (mental model):**
- Account numbers, not names: "konto 1920", "konto 3000"
- Debit/credit thinking: "debet 1920, kredit 3000"
- "Bilag" (voucher) is the fundamental unit of work
- "Bokfør" = post/book a voucher entry
- "Avstem" = reconcile
- "Korriger" = correct an error

---

## 2. API Endpoints — Full Details

### 2.1 Ledger Accounts (`/ledger/account`)

**Purpose:** Chart of accounts — every account in the company's bookkeeping.

| Method | Path | Required Params | Notes |
|--------|------|----------------|-------|
| GET | `/ledger/account` | none | `?number=1920` for specific account. `?isBankAccount=true` for bank accounts. `?numberFrom=X&numberTo=Y` does NOT work in sandbox (returns all). |
| PUT | `/ledger/account/{id}` | id, version, number, name | Used to set bankAccountNumber on 1920. |

**Sandbox state:** 2 bank accounts (1920 Bankinnskudd, 1950 Skattetrekk). Total ~2800 accounts.

**Key accounts for accountant workflows:**

| Number | Name | Role |
|--------|------|------|
| 1500 | Kundefordringer | Accounts receivable |
| 1700 | Forskuddsbetalt leiekostnad | Prepaid rent |
| 1920 | Bankinnskudd | Primary bank account (id=436982614) |
| 1950 | Bankinnskudd for skattetrekk | Tax withholding bank |
| 2000 | Aksjekapital | Share capital |
| 2050 | Annen egenkapital | Other equity (id=436982627) — **year-end target** |
| 2400 | Leverandørgjeld | Accounts payable |
| 2500 | Betalbar skatt | Tax payable |
| 2700 | Utgående mva, høy sats | Output VAT 25% (id=436982687) |
| 2710 | Inngående mva, høy sats | Input VAT 25% (id=436982695) |
| 2740 | Oppgjørskonto mva | VAT settlement (id=436982700) |
| 2780 | Påløpt AGA | Accrued employer's NI |
| 3000 | Salgsinntekt, avgiftspliktig | Sales revenue (taxable) |
| 3100 | Salgsinntekt, avgiftsfri | Sales revenue (exempt) |
| 4000 | Innkjøp råvarer | Raw material purchases |
| 5000 | Lønn til ansatte | Salaries |
| 6300 | Leie lokale | Office rent |
| 6800 | Kontorrekvisita | Office supplies |
| 7000 | Drivstoff | Fuel |
| 8050 | Annen renteinntekt | Interest income |
| 8300 | Betalbar skatt | Tax expense |
| 8960 | Overføringer annen egenkapital | Equity transfer (id=436983007) — **year-end source** |

---

### 2.2 Vouchers / Journal Entries (`/ledger/voucher`)

**Purpose:** The core accounting primitive — every financial event is a voucher with balanced postings.

| Method | Path | Required Params | Notes |
|--------|------|----------------|-------|
| GET | `/ledger/voucher` | `dateFrom`, `dateTo` (both REQUIRED, 422 otherwise) | Optional: `number`, `fields=*` |
| GET | `/ledger/voucher/{id}` | none | Direct lookup by ID |
| POST | `/ledger/voucher` | `date`, `description`, `postings[]` | Postings must balance (sum = 0). Each posting needs `account.id`, `amountGross`, `amountGrossCurrency`. |
| PUT | `/ledger/voucher/{id}/:reverse` | `?date=YYYY-MM-DD` | Creates automatic reversal voucher. **CONFIRMED WORKING** in sandbox! Returns new voucher with `reverseVoucher` ref. |
| DELETE | `/ledger/voucher/{id}` | none | Deletes unposted vouchers only. |

**Voucher response structure:**
```json
{
  "id": 608818357,
  "version": 4,
  "date": "2026-03-20",
  "number": 1,          // 0 = unposted (tempNumber used instead)
  "tempNumber": 3,
  "year": 2026,
  "description": "...",
  "voucherType": null,   // ref to voucherType
  "reverseVoucher": null, // set after /:reverse
  "postings": [{"id": N}],
  "numberAsString": "<Ikke bokført 3>"  // "Not posted 3" for unposted
}
```

**Gotchas:**
- `dateFrom` + `dateTo` are MANDATORY for GET list — 422 without them
- Unposted vouchers have `number=0` and use `tempNumber`
- `numberAsString` shows "Ikke bokført N" for unposted entries
- Reverse creates a NEW voucher with negated postings automatically
- Sandbox has 163 vouchers as of 2026-03-21
- `totalNumberOfPostings` field gives total posting count across all matched vouchers

---

### 2.3 Voucher Types (`/ledger/voucherType`)

**Purpose:** Categorize vouchers by type. Used for filtering and reporting.

| ID | Name (Norwegian) | English |
|----|-------------------|---------|
| 10155921 | Utgående faktura | Outgoing invoice |
| 10155922 | Leverandørfaktura | Supplier invoice |
| 10155923 | Purring | Reminder/dunning |
| 10155924 | Betaling | Payment |
| 10155925 | Lønnsbilag | Salary voucher |
| 10155926 | Terminoppgave | Tax return |
| 10155927 | Mva-melding | VAT report |
| 10155928 | Betaling med KID-nummer | Payment with KID |
| 10155929 | Remittering | Remittance |
| 10155930 | Bankavstemming | Bank reconciliation |
| 10155931 | Reiseregning | Travel expense |
| 10155932 | Ansattutlegg | Employee expense |
| 10155933 | Åpningsbalanse | Opening balance |
| 10155934 | Tolldeklarasjon | Customs declaration |
| 10155935 | Pensjon | Pension |
| 10155936 | Refusjon av sykepenger | Sick pay refund |
| 10155937 | (id only — likely "Annet/Other") | Other |

**Usage:** Pass `"voucherType": {"id": N}` in POST `/ledger/voucher`.

---

### 2.4 Ledger Postings (`/ledger/posting`)

**Purpose:** Individual debit/credit lines within vouchers.

| Method | Path | Required Params | Notes |
|--------|------|----------------|-------|
| GET | `/ledger/posting` | `dateFrom`, `dateTo` | Optional: `accountNumberFrom`, `accountNumberTo`, `voucherId` |

**Posting response structure:**
```json
{
  "id": 3844900067,
  "voucher": {"id": 608818357},
  "date": "2026-03-20",
  "description": "Test debit",
  "account": {"id": 436982614},
  "employee": {"id": 18491802},
  "amount": 1000.0,
  "amountCurrency": 1000.0,
  "amountGross": 1000.0,
  "amountGrossCurrency": 1000.0,
  "currency": {"id": 1},      // 1=NOK
  "vatType": {"id": 0},
  "row": 1,
  "matched": false,
  "closeGroup": null,
  "systemGenerated": false,
  "freeAccountingDimension1": null,
  "freeAccountingDimension2": null,
  "freeAccountingDimension3": null
}
```

**Gotchas:**
- `employee.id` is required on each posting when creating vouchers (validated by API)
- `row` must be >= 1 (row 0 is system-reserved)
- `amount` vs `amountGross`: amountGross includes VAT, amount is net
- `freeAccountingDimension1-3` are for custom accounting dimensions

---

### 2.5 VAT Types (`/ledger/vatType`)

**Purpose:** Norwegian MVA (merverdiavgift) classification.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/ledger/vatType` | Returns all VAT types. ~50 types in sandbox. |

**Key types for everyday accounting:**

| ID | Code | Rate | Name | Use case |
|----|------|------|------|----------|
| 0 | 0 | 0% | Ingen avgiftsbehandling | Default, no VAT |
| 1 | 1 | 25% | Fradrag inngående, høy sats | Input VAT (purchases) — deductible |
| 3 | 3 | 25% | Utgående avgift, høy sats | Output VAT (sales) |
| 5 | 5 | 0% | Ingen utgående (innenfor mva-loven) | Exempt within MVA law |
| 6 | 6 | 0% | Ingen utgående (utenfor mva-loven) | Outside MVA law |
| 7 | 7 | 0% | Ingen avgiftsbehandling (inntekter) | Income, no VAT |
| 11 | 11 | 15% | Fradrag inngående, middels sats | Food/beverage input |
| 12 | 13 | 12% | Fradrag inngående, lav sats | Transport input |
| 31 | 31 | 15% | Utgående, middels sats | Food sales output |
| 32 | 33 | 12% | Utgående, lav sats | Transport/cinema output |
| 81 | 81 | -25% | Fradrag innførsel, høy sats | Import deduction |
| 82 | 82 | -25% | Uten fradrag innførsel | Import without deduction |
| 550 | TAP-1 | 25% | Tap på krav | Bad debt loss |

**Gotchas:**
- VAT type id=3 (25% outgoing) is REJECTED for product creation but valid for voucher postings
- Negative percentages (-25%, -15%, -12%) are for reverse charge / import scenarios
- "Direktepostert" types (id=2,4) post VAT directly to the account (bypasses settlement)

---

### 2.6 Accounting Periods (`/ledger/accountingPeriod`)

**Purpose:** Monthly accounting periods for closing and reconciliation.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/ledger/accountingPeriod` | Returns all periods for current fiscal year |

**Sandbox periods (2026):**

| ID | Name | Number | Start | End | isClosed |
|----|------|--------|-------|-----|----------|
| 23731256 | Januar | 0 | 2026-01-01 | 2026-02-01 | false |
| 23731257 | Februar | 1 | 2026-02-01 | 2026-03-01 | false |
| 23731258 | Mars | 2 | 2026-03-01 | 2026-04-01 | false |
| 23731259 | April | 3 | 2026-04-01 | 2026-05-01 | false |
| ... | ... | ... | ... | ... | false |

**Important:** `end` date is exclusive (Feb period: 2026-02-01 to 2026-03-01 means Feb only).

---

### 2.7 Bank Reconciliation (`/bank/reconciliation`)

**Purpose:** Match bank statement transactions to ledger postings.

| Method | Path | Required Params | Notes |
|--------|------|----------------|-------|
| GET | `/bank/reconciliation` | none | Lists existing reconciliations |
| POST | `/bank/reconciliation` | `account.id`, `accountingPeriod.id`, `type` | Creates new reconciliation. type: "MANUAL" or "AUTO" |
| GET | `/bank/reconciliation/match` | none | Lists matched transactions |
| POST | `/bank/reconciliation/match` | `bankReconciliation.id`, `transactions[]` (with IDs), `postings[]` | Match postings to transactions |

**Bank Reconciliation Response:**
```json
{
  "id": 12705337,
  "account": {"id": 436982614},          // ledger account 1920
  "accountingPeriod": {"id": 23731256},   // January period
  "voucher": null,
  "transactions": [],
  "isClosed": false,
  "type": "MANUAL",
  "bankAccountClosingBalanceCurrency": 0.0,
  "closedDate": null,
  "approvable": false,
  "autoPayReconciliation": false
}
```

**Bank Reconciliation Payment Types:**

| ID | Description | Debit Account |
|----|-------------|---------------|
| 33998612 | Bankgebyr | 436982944 (konto 7770 Bankgebyr) |
| 33998613 | Kortgebyr | 436982944 |

**Gotchas:**
- POST `/bank/reconciliation/match` requires `transactions` with actual transaction IDs (from bank statement import)
- `/bankStatement` returns 404 in sandbox (no imported bank statements)
- Without bank statement import, reconciliation is manual (create vouchers to match)
- `accountingPeriod.id` is required — must look up via GET `/ledger/accountingPeriod`

---

### 2.8 Close Groups (`/ledger/closeGroup`)

**Purpose:** Groups of postings that are closed together (period closing).

| Method | Path | Required Params | Notes |
|--------|------|----------------|-------|
| GET | `/ledger/closeGroup` | `dateFrom`, `dateTo` | Lists close groups with posting refs |

**Response structure:**
```json
{
  "id": 282709523,
  "date": "2026-03-20",
  "postings": [
    {"id": 3844900059},
    {"id": 3844900061}
  ]
}
```

---

### 2.9 Annual Account (`/ledger/annualAccount`)

**Purpose:** Year-end closing management.

| Method | Path | Required Params | Notes |
|--------|------|----------------|-------|
| GET | `/ledger/annualAccount` | `yearFrom`, `yearTo` | No data in sandbox (empty result set) |
| PUT | `/ledger/annualAccount/{id}/:close` | none | Close an annual account |

**Sandbox state:** Empty — no annual accounts exist. Year-end closing must be done via voucher approach.

---

### 2.10 Balance Sheet (`/balanceSheet`)

**Purpose:** Report showing assets, liabilities, and equity at a point in time.

| Method | Path | Required Params | Notes |
|--------|------|----------------|-------|
| GET | `/balanceSheet` | `dateFrom`, `dateTo` | Returns account-level balance changes |

**Response structure:**
```json
{
  "account": {"id": 436982558},
  "balanceIn": 0.0,
  "balanceChange": 826448.0,
  "balanceOut": 826448.0,
  "startDate": "2026-01-01",
  "endDate": "2026-03-31"
}
```

---

### 2.11 Accounting Dimensions (`/ledger/accountingDimensionName`, `/ledger/accountingDimensionValue`)

**Purpose:** Custom tracking dimensions (kostsenter, region, etc.) — up to 3 slots.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/ledger/accountingDimensionName` | Lists dimension definitions |
| POST | `/ledger/accountingDimensionName` | Create dimension |
| PUT | `/ledger/accountingDimensionName/{id}` | Rename/update dimension |
| GET | `/ledger/accountingDimensionValue` | Lists values for a dimension |
| POST | `/ledger/accountingDimensionValue` | Create a value |

**Sandbox state:**
- Slot 1 (id=930): "Kostnadssted" (Cost center) — active
- Slot 2 (id=941): "Region" — active
- Slot 3: potentially available

**Usage in voucher postings:** Set `freeAccountingDimension1`, `freeAccountingDimension2`, or `freeAccountingDimension3` on posting objects.

---

## 3. Workflow Sequences — Step-by-Step API Calls

### 3.1 Daily Bank Transaction Recording

**Scenario:** "Bokfør bankbevegelse: Mottatt betaling 15 000 kr fra kunde Acme AS"

```
1. GET /ledger/account?number=1920
   → account_id for bank account

2. GET /ledger/account?number=1500
   → account_id for kundefordringer (accounts receivable)

3. POST /ledger/voucher
   {
     "date": "2026-03-21",
     "description": "Innbetaling fra Acme AS",
     "voucherType": {"id": 10155924},  // "Betaling"
     "postings": [
       {"account": {"id": <1920_id>}, "amountGross": 15000, "amountGrossCurrency": 15000,
        "currency": {"id": 1}, "description": "Bank inn", "date": "2026-03-21", "row": 1},
       {"account": {"id": <1500_id>}, "amountGross": -15000, "amountGrossCurrency": -15000,
        "currency": {"id": 1}, "description": "Kundefordring", "date": "2026-03-21", "row": 2}
     ]
   }
```

**API calls: 3** (2 account lookups + 1 voucher creation)

---

### 3.2 Supplier Invoice Booking (Leverandørfaktura)

**Scenario:** "Bokfør faktura fra Staples: kontorekvisita 2500 kr + mva 25%"

```
1. GET /ledger/account?number=6800    → office supplies account
2. GET /ledger/account?number=2400    → accounts payable
3. GET /ledger/account?number=2710    → input VAT account

4. POST /ledger/voucher
   {
     "date": "2026-03-21",
     "description": "Leverandørfaktura Staples - kontorekvisita",
     "voucherType": {"id": 10155922},  // "Leverandørfaktura"
     "postings": [
       {"account": {"id": <6800_id>}, "amountGross": 2500,
        "vatType": {"id": 1}, "description": "Kontorekvisita", "row": 1},
       {"account": {"id": <2710_id>}, "amountGross": 625,
        "description": "Inng. mva 25%", "row": 2},
       {"account": {"id": <2400_id>}, "amountGross": -3125,
        "description": "Leverandørgjeld Staples", "row": 3}
     ]
   }
```

**API calls: 4** (3 account lookups + 1 voucher). Note: with VAT type on the expense posting, Tripletex may auto-calculate the VAT posting — test both approaches.

---

### 3.3 Bank Reconciliation Workflow

**Scenario:** "Utfør bankavstemming for konto 1920, mars 2026"

```
1. GET /ledger/account?number=1920
   → account_id = 436982614

2. GET /ledger/accountingPeriod
   → Find period for Mars (id=23731258, start=2026-03-01, end=2026-04-01)

3. POST /bank/reconciliation
   {
     "account": {"id": 436982614},
     "accountingPeriod": {"id": 23731258},
     "type": "MANUAL"
   }
   → reconciliation_id

4. GET /ledger/posting?dateFrom=2026-03-01&dateTo=2026-03-31&accountId=436982614
   → List all postings on bank account for the period

5. (Optional) POST /bank/reconciliation/match
   → Match specific postings to bank statement transactions
   (Requires bank statement import — may not work in sandbox)
```

**API calls: 3-5**

**Important:** In sandbox, `/bankStatement` returns 404 (no imported statements). The practical approach is to create the reconciliation + log vouchers for any unmatched transactions.

---

### 3.4 Error Correction / Voucher Reversal

**Scenario:** "Korriger feilpostering på bilag 1 i 2026"

```
1. GET /ledger/voucher?dateFrom=2026-01-01&dateTo=2026-12-31&number=1
   → Find voucher by number, get voucher_id

   OR: GET /ledger/voucher/{id} if ID is known directly

2. PUT /ledger/voucher/{voucher_id}/:reverse?date=2026-03-21
   → Creates automatic reversal voucher
   Response: new voucher with reverseVoucher pointing to original

3. (Optional) POST /ledger/voucher
   → Create corrected entry with correct postings
```

**CONFIRMED:** `:reverse` endpoint works in sandbox! Returns:
```json
{
  "id": 608895057,
  "description": "Reversering av bilag 1-2026. <original description>",
  "reverseVoucher": {"id": 608818357}
}
```

**API calls: 2-3** (find + reverse + optional correction)

**Fallback chain (if `:reverse` fails):**
1. Try DELETE `/ledger/voucher/{id}` (only works for unposted)
2. Create manual reversal voucher with negated postings

---

### 3.5 VAT Reporting / Settlement (Mva-melding)

**Scenario:** "Opprett mva-oppgjør for termin 1 2026 (jan-feb)"

```
1. GET /ledger/posting?dateFrom=2026-01-01&dateTo=2026-02-28
   &accountNumberFrom=2700&accountNumberTo=2710
   → Sum up output VAT (2700) and input VAT (2710)

2. Calculate: Netto mva = Utgående (2700) - Inngående (2710)

3. POST /ledger/voucher
   {
     "date": "2026-03-10",
     "description": "Mva-oppgjør termin 1 2026",
     "voucherType": {"id": 10155927},  // "Mva-melding"
     "postings": [
       {"account": {"id": <2700_id>}, "amountGross": -<output_vat>,
        "description": "Nullstill utg. mva", "row": 1},
       {"account": {"id": <2710_id>}, "amountGross": <input_vat>,
        "description": "Nullstill inng. mva", "row": 2},
       {"account": {"id": <2740_id>}, "amountGross": <net_vat>,
        "description": "Mva til betaling", "row": 3}
     ]
   }
   → Transfers VAT to settlement account (2740)

4. (When paying) POST /ledger/voucher
   {
     "date": "2026-04-10",
     "description": "Betaling mva termin 1",
     "voucherType": {"id": 10155924},
     "postings": [
       {"account": {"id": <2740_id>}, "amountGross": -<net_vat>, "row": 1},
       {"account": {"id": <1920_id>}, "amountGross": <net_vat>, "row": 2}
     ]
   }
```

**API calls: 3-5** (posting lookup + account lookups + voucher creation)

**Key accounts:**
- 2700: Utgående mva, høy sats (id=436982687)
- 2710: Inngående mva, høy sats (id=436982695)
- 2740: Oppgjørskonto mva (id=436982700)

---

### 3.6 Year-End Closing (Årsavslutning)

**Scenario:** "Opprett årsavslutning for 2025"

```
1. GET /ledger/annualAccount?yearFrom=2025&yearTo=2025
   → Check for existing annual account (likely empty in sandbox)

2. GET /ledger/posting?dateFrom=2025-01-01&dateTo=2025-12-31
   &accountNumberFrom=3000&accountNumberTo=8999
   → Sum all P&L postings to get net result

3. GET /ledger/account?number=8960
   → "Overføringer annen egenkapital" (id=436983007)

4. GET /ledger/account?number=2050
   → "Annen egenkapital" (id=436982627)

5. GET /ledger/voucherType (find årsavslutning type)

6. POST /ledger/voucher
   {
     "date": "2025-12-31",
     "description": "Årsavslutning 2025 - Overføring av årsresultat til egenkapital",
     "voucherType": {"id": <type_id>},
     "postings": [
       {"account": {"id": 436983007}, "amountGross": -<net_result>,
        "description": "Årsresultat 2025", "date": "2025-12-31", "row": 1},
       {"account": {"id": 436982627}, "amountGross": <net_result>,
        "description": "Overført til egenkapital 2025", "date": "2025-12-31", "row": 2}
     ]
   }
```

**API calls: 5-6** (annual account check + P&L postings + 2 account lookups + voucher type + voucher creation)

**Notes:**
- `/ledger/annualAccount` is empty in sandbox → must use voucher approach
- Equity transfer: 8960 → 2050 (both confirmed present in sandbox)
- If profit: debit 8960, credit 2050 (positive amount on 2050)
- If loss: debit 2050, credit 8960 (negative amount on 2050)

---

### 3.7 Dimension Voucher (Bokfør med Dimensjon)

**Scenario:** "Bokfør bilag med kostsenter 'Salg' på konto 7000 debet, 2400 kredit, 3000 kr"

```
1. GET /ledger/accountingDimensionName?fields=*
   → Find "Kostnadssted" dimension (id=930, slot 1)

2. GET /ledger/accountingDimensionValue?dimensionId=930
   → Find "Salg" value or create it

3. (If not found) POST /ledger/accountingDimensionValue
   {"dimensionName": {"id": 930}, "valueName": "Salg"}

4. GET /ledger/account?number=7000 → debit account
5. GET /ledger/account?number=2400 → credit account

6. POST /ledger/voucher
   {
     "date": "2026-03-21",
     "description": "Drivstoff - Kostsenter Salg",
     "postings": [
       {"account": {"id": <7000_id>}, "amountGross": 3000,
        "freeAccountingDimension1": {"id": <salg_value_id>},
        "description": "Drivstoff", "row": 1},
       {"account": {"id": <2400_id>}, "amountGross": -3000,
        "description": "Leverandørgjeld", "row": 2}
     ]
   }
```

**API calls: 4-6**

---

## 4. Prompt Patterns — Norwegian + English

### 4.1 Voucher / Journal Entry Posting (Bokføring)

**Norwegian:**
- "Bokfør bilag med konto 1920 debet og 3000 kredit, beløp 5000 kr"
- "Bokfør en innbetaling på 15 000 kr fra kunde Acme AS til bankkonto"
- "Post leverandørfaktura fra Staples: 2500 kr kontorekvisita pluss mva"
- "Opprett bilag: debet 6300 leie 10000 kr, kredit 1920 bank"
- "Bokfør lønn for mars: debet 5000 lønn 45000 kr, kredit 1920 bank"
- "Registrer bankgebyr 150 kr"
- "Bokfør avskrivning 50 000 kr på konto 6000 mot 1000"

**English:**
- "Post a journal entry: debit 1920 bank, credit 3000 sales, amount 5000 NOK"
- "Book a supplier invoice from Office Corp: 2500 kr office supplies with 25% VAT"
- "Record a bank transaction: received 15000 kr payment from customer"
- "Create voucher: debit account 6300 rent 10000, credit 1920 bank"

**German:**
- "Buche einen Beleg: Konto 1920 Soll, Konto 3000 Haben, Betrag 5000 NOK"
- "Erstelle eine Buchung für Lieferantenrechnung von Staples: 2500 NOK Bürobedarf"

### 4.2 Bank Reconciliation (Bankavstemming)

**Norwegian:**
- "Utfør bankavstemming for konto 1920"
- "Avstem bankkonto for mars 2026"
- "Bankavstemming for periode januar-mars 2026"
- "Opprett manuell bankavstemming for konto 1920, mars 2026"

**English:**
- "Reconcile bank account 1920 for March 2026"
- "Perform bank reconciliation for the current period"
- "Create manual bank reconciliation for account 1920"

### 4.3 Error Correction (Feilretting)

**Norwegian:**
- "Korriger feilpostering på bilag 12345"
- "Reverser bilag nummer 5 i 2026"
- "Rett opp feil i bilag fra mars — feil konto brukt"
- "Korriger bilag 3: ble ført på 6300, skal være 6800"
- "Slett bilag 7 — ble ført dobbelt"

**English:**
- "Correct error in voucher 12345"
- "Reverse voucher number 5 for 2026"
- "Fix posting error: wrong account used on voucher 3"

### 4.4 Year-End Closing (Årsavslutning)

**Norwegian:**
- "Opprett årsavslutning for 2025"
- "Utfør årsoppgjør for regnskapsåret 2025"
- "Bokfør årsavslutningsbilag for 2025"
- "Overfør årsresultat til egenkapital for 2025"

**English:**
- "Perform year-end closing for fiscal year 2025"
- "Create closing entries for 2025"
- "Transfer profit/loss to equity for year-end 2025"

### 4.5 VAT Reporting (Mva-melding)

**Norwegian:**
- "Opprett mva-oppgjør for termin 1 2026"
- "Beregn merverdiavgift for januar-februar 2026"
- "Bokfør mva-melding for mars 2026"
- "Nullstill mva-kontoer og overfør til oppgjørskonto"

**English:**
- "Create VAT settlement for term 1, 2026"
- "Calculate and post VAT report for January-February 2026"
- "Post VAT return for Q1 2026"

### 4.6 Dimension Vouchers

**Norwegian:**
- "Bokfør bilag med kostsenter Salg, konto 7000 debet 3000 kr"
- "Opprett dimensjonsbilag med region Nord"
- "Bokfør drivstoff 3000 kr på kostsenter Drift"
- "Legg til fri dimensjon 'Prosjekttype' med verdier Intern, Ekstern"

**English:**
- "Create a voucher with cost center 'Sales' on account 7000"
- "Post an expense with accounting dimension 'Region' = 'North'"
- "Add custom dimension 'Project Type' with values Internal, External"

---

## 5. Gap Analysis — What Our Agent Cannot Handle

### 5.1 Missing Task Types (Not in our 30 types)

| Workflow | Status | Impact |
|----------|--------|--------|
| **Post general voucher/bilag** | PARTIALLY covered by `CREATE_DIMENSION_VOUCHER` | Most common accountant task! Needs dedicated `CREATE_VOUCHER` task type for simple debit/credit postings without dimensions |
| **VAT settlement/reporting** | NOT COVERED | High — accountants do this every other month (6 terms/year) |
| **Period closing** | NOT COVERED | Separate from year-end — monthly close |
| **Balance sheet report** | NOT COVERED | Accountants check this frequently |
| **Trial balance (saldobalanse)** | NOT COVERED | Core verification tool |
| **Ledger posting query** | NOT COVERED | "Vis alle posteringer på konto 1920 i mars" |
| **Bank statement import** | NOT POSSIBLE | Sandbox doesn't support `/bankStatement` |

### 5.2 Existing Task Types — Improvement Opportunities

| Task | Issue | Fix |
|------|-------|-----|
| `BANK_RECONCILIATION` | Handles transactions but `bankStatement` endpoint returns 404 in sandbox. Match endpoint requires transaction IDs from imported statements. | Focus on manual reconciliation: verify account balance, create vouchers for unmatched items |
| `ERROR_CORRECTION` | `:reverse` WORKS but handler has 3 fallback paths with lots of API calls. | Simplify: try `:reverse` first (confirmed working), only fall back if it fails |
| `YEAR_END_CLOSING` | `/ledger/annualAccount` is empty in sandbox. Current handler tries 3 approaches. | Go directly to voucher approach (P&L to equity via 8960→2050). Skip annual account and close group attempts. |
| `CREATE_DIMENSION_VOUCHER` | Actually handles basic voucher posting too, but name implies it's only for dimensions | Rename or add `CREATE_VOUCHER` alias for simple postings |
| `CREATE_SUPPLIER_INVOICE` | Creates voucher but may not match how accountants think about it | Add explicit debit/credit account extraction from prompts |

### 5.3 Classifier Gaps

| Pattern | Current Handling | Needed |
|---------|-----------------|--------|
| "Bokfør bilag..." | May route to `CREATE_DIMENSION_VOUCHER` | Needs reliable routing for all "bokfør" patterns |
| "Vis saldo på konto X" | Not handled | New task type: `QUERY_BALANCE` |
| "Mva-oppgjør" / "Terminoppgave" | Not handled | New task type: `VAT_SETTLEMENT` |
| "Saldobalanse" | Not handled | New task type: `TRIAL_BALANCE` |
| "Lukk periode" | Not handled | New task type: `CLOSE_PERIOD` |
| Account number mentions (1920, 3000, etc.) | Not extracted by classifier | Add account number extraction pattern |

### 5.4 Sandbox Limitations

| Feature | Status | Workaround |
|---------|--------|------------|
| Bank statement import | 404 | Can't test real reconciliation flow |
| Annual accounts | Empty | Use voucher approach for year-end |
| `numberFrom`/`numberTo` on accounts | Broken (returns all) | Use `?number=XXXX` for exact lookup |
| Close period API | Unknown | May need voucher-based approach |
| VAT report submission | Unknown | Can create settlement vouchers |

---

## 6. Recommendations

### 6.1 High Priority — Tier 3 Score Impact (×3 multiplier)

1. **Optimize `ERROR_CORRECTION` handler:**
   - `:reverse` is CONFIRMED WORKING. Make it the primary path.
   - Remove excessive fallback chains that waste API calls (hurts efficiency bonus).
   - Parse "bilag N" more aggressively — accountants use voucher numbers, not IDs.

2. **Optimize `YEAR_END_CLOSING` handler:**
   - Skip `/ledger/annualAccount` (always empty in sandbox).
   - Go directly to voucher approach: 8960→2050 equity transfer.
   - Saves 1-2 wasted API calls → better efficiency score.

3. **Optimize `BANK_RECONCILIATION` handler:**
   - Don't try `/bankStatement` (always 404).
   - Focus on: create reconciliation entry + create vouchers for transactions.
   - Use correct `accountingPeriod.id` from period lookup.

4. **Improve `CREATE_DIMENSION_VOUCHER` / general voucher posting:**
   - Add classifier patterns for simple "bokfør" without dimension keywords.
   - Extract account numbers from prompts: `r"(?:konto|account)\s*(\d{4})"`.
   - Extract debit/credit from prompts: `r"(debet|debit|soll).*(\d{4}).*(?:kredit|credit|haben).*(\d{4})"`.

### 6.2 Medium Priority — New Capabilities

5. **Add `VAT_SETTLEMENT` task type:**
   - Classifier keywords: "mva-oppgjør", "terminoppgave", "mva-melding", "VAT settlement"
   - Flow: Query postings on 2700/2710 → Create settlement voucher → Transfer to 2740
   - Use voucherType id=10155927 ("Mva-melding")

6. **Add `CREATE_VOUCHER` task type (or alias):**
   - Most accountant tasks are "bokfør bilag" — simple debit/credit entries
   - Currently handled by `CREATE_DIMENSION_VOUCHER` but naming is confusing
   - Need robust account number extraction from Norwegian prompts

### 6.3 Classifier Improvements

7. **Norwegian accounting terminology patterns:**
   ```
   "bokfør" → CREATE_VOUCHER or CREATE_DIMENSION_VOUCHER
   "bilag" → voucher-related task
   "konto \d{4}" → account number extraction
   "debet.*kredit" → voucher posting with explicit accounts
   "mva" + "oppgjør|melding|termin" → VAT_SETTLEMENT
   "saldobalanse" → TRIAL_BALANCE (new)
   "avstem" → BANK_RECONCILIATION
   "reverser|korriger" + "bilag" → ERROR_CORRECTION
   "årsavslut|årsoppgjør" → YEAR_END_CLOSING
   ```

8. **Account number extraction from prompts:**
   - Pattern: `r"(?:konto|account|kto\.?)\s*(\d{4})"`
   - Map to standard accounts: 1920=bank, 1500=AR, 2400=AP, 3000=sales, etc.

### 6.4 Efficiency Optimizations

9. **Cache account lookups across calls:**
   - Account IDs don't change within a request
   - Current code already has some caching but may re-lookup common accounts (1920, 2050, etc.)

10. **Minimize API calls on year-end:**
    - Current: tries annual account (404) → tries close (fail) → tries PUT (fail) → falls back to voucher
    - Optimized: jump straight to voucher approach (3 calls: 2 account lookups + 1 voucher)

---

## Appendix A: Voucher Type ID Reference

```
10155921 = Utgående faktura (Outgoing invoice)
10155922 = Leverandørfaktura (Supplier invoice)
10155923 = Purring (Reminder)
10155924 = Betaling (Payment)
10155925 = Lønnsbilag (Salary)
10155926 = Terminoppgave (Tax return)
10155927 = Mva-melding (VAT report)
10155928 = Betaling med KID (KID payment)
10155929 = Remittering (Remittance)
10155930 = Bankavstemming (Bank reconciliation)
10155931 = Reiseregning (Travel expense)
10155932 = Ansattutlegg (Employee expense)
10155933 = Åpningsbalanse (Opening balance)
10155934 = Tolldeklarasjon (Customs)
10155935 = Pensjon (Pension)
10155936 = Refusjon sykepenger (Sick pay refund)
```

## Appendix B: Key Account IDs (Sandbox)

```
436982614 = 1920 Bankinnskudd
436982558 = 1500-range (verify)
436982627 = 2050 Annen egenkapital
436982687 = 2700 Utgående mva høy sats
436982695 = 2710 Inngående mva høy sats
436982700 = 2740 Oppgjørskonto mva
436982711 = 3000-range (verify)
436982944 = 7770 Bankgebyr
436983007 = 8960 Overføringer annen egenkapital
```

## Appendix C: Currency IDs

```
1=NOK, 2=SEK, 3=DKK, 4=USD, 5=EUR, 6=GBP, 7=CHF
```
