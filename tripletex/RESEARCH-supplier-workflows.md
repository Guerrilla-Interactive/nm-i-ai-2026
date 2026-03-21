# Supplier Manager Workflows — Tripletex API Research

**Date:** 2026-03-21
**Sandbox:** `https://kkpqfuj-amager.tripletex.dev/v2`

---

## 1. User Persona: Innkjøpsansvarlig (Supplier Manager)

The Supplier Manager (Innkjøpsansvarlig) handles:
- Registering and maintaining suppliers
- Receiving and booking incoming invoices (leverandørfakturaer)
- Approving supplier invoices for payment
- Processing supplier payments
- Tracking accounts payable (leverandørgjeld)
- Cost allocation by department/project
- Purchase order management

Common Norwegian titles: Innkjøpsansvarlig, Regnskapsansvarlig, Økonomimedarbeider

---

## 2. API Endpoints — Full Details

### 2.1 Supplier CRUD

| Method | Path | Description |
|--------|------|-------------|
| GET | `/supplier` | Search suppliers |
| POST | `/supplier` | Create supplier |
| POST | `/supplier/list` | Create multiple suppliers |
| GET | `/supplier/{id}` | Get supplier by ID |
| PUT | `/supplier/{id}` | Update supplier |
| PUT | `/supplier/list` | Update multiple suppliers |
| DELETE | `/supplier/{id}` | Delete supplier |
| GET | `/supplierCustomer/search` | Search across suppliers AND customers |

**GET /supplier query params:**
- `id` — List of IDs (comma-separated)
- `supplierNumber` — List of IDs
- `organizationNumber` — Exact match
- `email` — Exact match
- `invoiceEmail` — Exact match
- `isInactive` — Boolean filter
- `accountManagerId` — List of IDs
- `changedSince` — ISO timestamp
- `isWholesaler` — Boolean
- `showProducts` — Boolean

**IMPORTANT: No `name` query param exists on GET /supplier!**
The API does NOT support name-based search on the `/supplier` endpoint. Our code uses `name` param which silently returns all suppliers (param is ignored). Use `organizationNumber` or iterate results client-side.

**POST /supplier minimal payload:**
```json
{"name": "Byggmester AS"}
```

**POST /supplier full payload:**
```json
{
  "name": "Byggmester AS",
  "organizationNumber": "912345678",
  "email": "faktura@byggmester.no",
  "invoiceEmail": "faktura@byggmester.no",
  "phoneNumber": "22334455",
  "supplierNumber": 50010,
  "currency": {"id": 1},
  "language": "NO",
  "postalAddress": {
    "addressLine1": "Industriveien 1",
    "postalCode": "0150",
    "city": "Oslo",
    "country": {"id": 161}
  }
}
```

**Existing suppliers in sandbox:**
| ID | Number | Name | Org Number |
|----|--------|------|------------|
| 108269521 | 50005 | Wave4 Supplies AS | — |
| 108269529 | 50006 | Global Parts Inc | — |
| 108284283 | 50007 | Staples Norge AS | 912345678 |
| 108286903 | 50008 | Bürobedarf Schmidt | 444555666 |
| 108332919 | 50009 | Acme Leverandør AS | 987654321 |

### 2.2 Supplier Invoice Endpoints

**CRITICAL DISCOVERY: There is NO POST /supplierInvoice endpoint.**

Supplier invoices are created via **POST /ledger/voucher** with appropriate voucherType and postings. The `/supplierInvoice` endpoints are for reading, approving, and managing existing supplier invoices.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/supplierInvoice` | Search supplier invoices (requires `invoiceDateFrom` + `invoiceDateTo`) |
| GET | `/supplierInvoice/{id}` | Get by ID |
| GET | `/supplierInvoice/forApproval` | Get invoices pending approval |
| GET | `/supplierInvoice/{invoiceId}/pdf` | Download PDF |
| PUT | `/supplierInvoice/{invoiceId}/:approve` | Approve single invoice |
| PUT | `/supplierInvoice/:approve` | Approve multiple invoices |
| PUT | `/supplierInvoice/{invoiceId}/:reject` | Reject single invoice |
| PUT | `/supplierInvoice/:reject` | Reject multiple invoices |
| PUT | `/supplierInvoice/{invoiceId}/:addRecipient` | Add approval recipient |
| PUT | `/supplierInvoice/:addRecipient` | Add recipient to many |
| PUT | `/supplierInvoice/{invoiceId}/:changeDimension` | Change dimension on invoice |
| PUT | `/supplierInvoice/voucher/{id}/postings` | [BETA] Put debit postings on voucher |
| POST | `/supplierInvoice/{invoiceId}/:addPayment` | Register payment on supplier invoice |

**GET /supplierInvoice query params:**
- `invoiceDateFrom` (REQUIRED) — From date
- `invoiceDateTo` (REQUIRED) — To date
- `id` — List of IDs
- `invoiceNumber` — Exact match
- `kid` — Exact match (KID number)
- `voucherId` — Exact match
- `supplierId` — Exact match

### 2.3 Voucher Endpoints (for creating supplier invoices)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ledger/voucher` | Create voucher with postings |
| PUT | `/ledger/voucher/{id}` | Update voucher |
| GET | `/ledger/voucher/{id}` | Get voucher |
| DELETE | `/ledger/voucher/{id}` | Delete voucher |
| PUT | `/ledger/voucher/{id}/:reverse` | Reverse voucher |
| PUT | `/ledger/voucher/{id}/:sendToLedger` | Send to ledger (post) |
| POST | `/ledger/voucher/importDocument` | Upload document to create voucher(s) |

### 2.4 Voucher Types (all 17)

| ID | Name |
|----|------|
| 10155921 | Utgående faktura |
| **10155922** | **Leverandørfaktura** ← USE THIS for supplier invoices |
| 10155923 | Purring |
| 10155924 | Betaling |
| 10155925 | Lønnsbilag |
| 10155926 | Terminoppgave |
| 10155927 | Mva-melding |
| 10155928 | Betaling med KID-nummer |
| 10155929 | Remittering |
| 10155930 | Bankavstemming |
| 10155931 | Reiseregning |
| 10155932 | Ansattutlegg |
| 10155933 | Åpningsbalanse |
| 10155934 | Tolldeklarasjon |
| 10155935 | Pensjon |
| 10155936 | Refusjon av sykepenger |
| 10155937 | (unknown – truncated) |

### 2.5 Payment Types

From `/invoice/paymentType` (incoming payments for customer invoices):
| ID | Description | Debit Account |
|----|-------------|---------------|
| 33998616 | Kontant | 436982611 |
| 33998617 | Betalt til bank | 436982614 (1920) |

**For supplier invoice payments:** Use POST `/supplierInvoice/{invoiceId}/:addPayment` with:
- `paymentType` (int, required) — Set to 0 to auto-detect last payment type for vendor
- `amount` (number)
- `paymentDate` (string)
- `useDefaultPaymentType` (boolean, default false)
- `partialPayment` (boolean, default false)
- `kidOrReceiverReference` (string)
- `bban` (string)

### 2.6 Accounts Applicable for Supplier Invoices

Total: **71 accounts** with `isApplicableForSupplierInvoice=true`

**Key accounts:**
| Number | ID | Name | VAT Type |
|--------|-----|------|----------|
| 1700 | 436982590 | Forskuddsbetalt leiekostnad | 0 (none) |
| 2400 | 436982673 | **Leverandørgjeld** | 0 (none) |
| 2713 | 436982698 | Direktepostert inng. MVA ved innførsel | 23 |
| **4000** | 436982775 | Innkjøp av råvarer og halvfabrikater | **1** (25% inng.) |
| 4100 | 436982779 | Innkjøp varer under tilvirkning | 1 |
| 4200 | 436982783 | Innkjøp ferdig egentilvirkede varer | 1 |
| **4300** | 436982787 | Innkjøp av varer for videresalg | **1** (25% inng.) |
| 4301 | 436982788 | Innkjøp videresalg, middels sats | 11 (15%) |
| 4400 | 436982794 | Innkjøp videresalg - utland | 13 |
| 4500 | 436982795 | Fremmedytelse og underentreprise | 1 |
| 6100–6290 | various | Transport, energi costs | 1 |
| **6300** | 436982869 | Leie lokale | 0 (exempt) |
| 6400–6490 | various | Equipment leasing | 1 |
| 6500–6590 | various | Tools, materials | 1 |
| 6600–6690 | various | Repairs, maintenance | 1 |
| 6701–6790 | various | Honorar (audit, legal, accounting) | 1 |
| **6800** | 436982901 | Kontorrekvisita | **1** (25% inng.) |
| 6810–6890 | various | Office, IT, courses | 1 |

---

## 3. Supplier Invoice Creation — THE EXACT PAYLOAD (CRITICAL)

### 3.1 The Correct Approach: POST /ledger/voucher

There is **NO dedicated POST /supplierInvoice** endpoint. Supplier invoices are created by posting a voucher with:
- `voucherType: {"id": 10155922}` (Leverandørfaktura)
- Debit posting on expense account (4000, 4300, 6800, etc.)
- Credit posting on account 2400 (Leverandørgjeld) with `supplier: {"id": N}`

### 3.2 Exact Payload — Simple (no VAT breakdown)

```json
POST /ledger/voucher?sendToLedger=true

{
  "date": "2026-03-21",
  "description": "Faktura fra Bygg AS - kontorrekvisita",
  "voucherType": {"id": 10155922},
  "postings": [
    {
      "date": "2026-03-21",
      "description": "Kontorrekvisita",
      "account": {"id": 436982901},
      "amountGross": 10000.0,
      "amountGrossCurrency": 10000.0,
      "currency": {"id": 1},
      "row": 1
    },
    {
      "date": "2026-03-21",
      "description": "Leverandørgjeld Bygg AS",
      "account": {"id": 436982673},
      "supplier": {"id": 108269521},
      "amountGross": -10000.0,
      "amountGrossCurrency": -10000.0,
      "currency": {"id": 1},
      "row": 2
    }
  ]
}
```

### 3.3 Exact Payload — With VAT (25% incoming MVA)

When `amountGross` is provided and the account has a VAT type, Tripletex auto-generates the VAT posting. The `amountGross` should be the **VAT-inclusive** amount. Only gross amounts are used per the API docs.

```json
POST /ledger/voucher?sendToLedger=true

{
  "date": "2026-03-21",
  "description": "Faktura fra Nordic Parts - varekjøp",
  "voucherType": {"id": 10155922},
  "postings": [
    {
      "date": "2026-03-21",
      "description": "Varekjøp",
      "account": {"id": 436982787},
      "amountGross": 25000.0,
      "amountGrossCurrency": 25000.0,
      "currency": {"id": 1},
      "row": 1
    },
    {
      "date": "2026-03-21",
      "description": "Leverandørgjeld Nordic Parts",
      "account": {"id": 436982673},
      "supplier": {"id": 108269529},
      "amountGross": -25000.0,
      "amountGrossCurrency": -25000.0,
      "currency": {"id": 1},
      "row": 2
    }
  ]
}
```

**Note:** When account 4300 (vatType=1, 25% incoming) is used with `amountGross=25000`:
- Tripletex auto-calculates: amountExclVAT = 20000, VAT = 5000
- System auto-generates a VAT posting to account 2710 (Inngående MVA)

### 3.4 Key Fields in Voucher Payload

| Field | Required | Description |
|-------|----------|-------------|
| `date` | YES | Voucher date (ISO: YYYY-MM-DD) |
| `description` | YES | Voucher description |
| `voucherType` | **SHOULD** | `{"id": 10155922}` for Leverandørfaktura. If omitted → null type, non-categorized |
| `vendorInvoiceNumber` | No | The supplier's own invoice number |
| `externalVoucherNumber` | No | External reference (max 70 chars) |
| `postings` | YES | Array of posting objects |

**Posting fields:**
| Field | Required | Description |
|-------|----------|-------------|
| `date` | YES | Posting date |
| `account` | YES | `{"id": N}` — ledger account reference |
| `amountGross` | YES | Gross amount (VAT-inclusive). Positive=debit, Negative=credit |
| `amountGrossCurrency` | YES | Same as amountGross for NOK |
| `currency` | No | `{"id": 1}` for NOK (default) |
| `row` | YES | Row number (≥1, row 0 is system-generated) |
| `description` | No | Posting description |
| `supplier` | **Credit row** | `{"id": N}` — MUST be set on the 2400 credit posting |
| `department` | No | `{"id": N}` for cost center allocation |
| `project` | No | `{"id": N}` for project allocation |
| `employee` | No | `{"id": N}` — NOT required (unlike regular vouchers) |
| `vatType` | No | Auto-detected from account's default vatType |
| `freeAccountingDimension1/2/3` | No | `{"id": N}` for custom dimensions |

### 3.5 sendToLedger Parameter

- `?sendToLedger=true` — Posts the voucher immediately (requires "Advanced Voucher" permission)
- `?sendToLedger=false` (default) — Creates voucher in "Ikke bokført" (not posted) state
- Our current code uses `send_to_ledger=False` → vouchers stay unposted!

### 3.6 The PUT /supplierInvoice/voucher/{id}/postings Endpoint (BETA)

This endpoint allows updating debit postings on an existing supplier invoice voucher:

```
PUT /supplierInvoice/voucher/{voucherId}/postings?sendToLedger=true&voucherDate=2026-03-21

Body: Array of OrderLinePosting objects
[
  {
    "orderLine": {"id": N},
    "posting": {
      "account": {"id": 436982787},
      "amountGross": 25000.0,
      ...
    }
  }
]
```

This is mainly useful for updating postings after document import, not for initial creation.

---

## 4. Supplier Lifecycle

```
1. CREATE SUPPLIER
   POST /supplier {"name":"X", "organizationNumber":"Y"}

2. RECEIVE INVOICE
   POST /ledger/voucher with voucherType=Leverandørfaktura
   - Debit: expense account (4000/4300/6800 etc.)
   - Credit: 2400 Leverandørgjeld with supplier ref

3. REVIEW & APPROVE
   PUT /supplierInvoice/{id}/:approve

4. PAY SUPPLIER
   POST /supplierInvoice/{invoiceId}/:addPayment
     ?paymentType=0&amount=N&paymentDate=YYYY-MM-DD
   (paymentType=0 auto-detects last type for vendor)

5. RECONCILE
   Bank reconciliation matches payment postings
```

### Alternative: Document Import Flow
```
1. POST /ledger/voucher/importDocument (upload PDF/image)
   → Tripletex OCR creates voucher automatically
2. PUT /supplierInvoice/voucher/{id}/postings
   → Correct/add debit postings
3. Approve → Pay → Reconcile
```

---

## 5. Payment Workflow

### 5.1 Paying a Supplier Invoice

```
POST /supplierInvoice/{invoiceId}/:addPayment
  ?paymentType=0
  &amount=10000
  &paymentDate=2026-03-21
  &useDefaultPaymentType=false
  &partialPayment=false
```

- `paymentType=0` → auto-finds last payment type for this vendor
- `partialPayment=true` → allows paying less than full amount
- `kidOrReceiverReference` → KID number for bank transfer
- `bban` → Bank account number

### 5.2 How Supplier Payment Differs from Customer Payment

| Aspect | Customer Payment | Supplier Payment |
|--------|-----------------|-----------------|
| Endpoint | `PUT /invoice/{id}/:payment` | `POST /supplierInvoice/{id}/:addPayment` |
| Direction | Money IN (debit bank, credit receivable) | Money OUT (debit payable, credit bank) |
| Payment types | Incoming: 33998616-33998619 | Different set (outgoing) |
| Account | Credit 1500 (Kundefordringer) | Debit 2400 (Leverandørgjeld) |
| Bank account | Debit 1920 | Credit 1920 |

### 5.3 Payment Type IDs

Payment types for supplier invoices may differ from customer invoice payment types. The `paymentType=0` auto-detection is the safest approach.

---

## 6. Prompt Patterns (Norwegian + English)

### 6.1 Register Supplier Invoice (CREATE_SUPPLIER_INVOICE)

**Norwegian:**
- "Registrer leverandørfaktura fra Bygg AS på 10000 kr"
- "Bokfør inngående faktura fra Nordic Parts, beløp 25000, konto 4300"
- "Vi har mottatt faktura fra Staples Norge AS på kr 5000 inkl. mva for kontorrekvisita"
- "Leverandørfaktura fra Wave4 Supplies, fakturanr 2026-001, 15000 kr ekskl. mva"
- "Registrer faktura fra leverandør Acme Leverandør AS, org.nr 987654321, 30000 kr"

**Nynorsk:**
- "Me har motteke faktura frå leverandøren Vestfjord AS på 45000 kr inkl. mva"

**English:**
- "Register supplier invoice from Global Parts Inc for 10000 NOK"
- "Book incoming invoice from Staples, 25000 NOK including VAT, account 4300"

**German:**
- "Eingangsrechnung von Bürobedarf Schmidt über 8000 NOK buchen"

**French:**
- "Enregistrer la facture fournisseur de Nordic Parts, montant 15000 NOK"

**Spanish:**
- "Registrar factura de proveedor Global Parts por 20000 NOK"

### 6.2 Create Supplier (CREATE_SUPPLIER)

**Norwegian:**
- "Opprett ny leverandør: Byggmester AS, org.nr 912345678"
- "Registrer leverandøren Havbris AS med org.nr. 987654321 og e-post: post@havbris.no"

**English:**
- "Create new supplier: Nordic Parts, org number 922976457, email: parts@nordic.com"

**German:**
- "Registrieren Sie den Lieferanten Nordlicht GmbH mit der Organisationsnummer 922976457"

### 6.3 Pay Supplier Invoice

**Norwegian:**
- "Betal leverandørfaktura 5001 med bankoverføring"
- "Registrer betaling på leverandørfaktura fra Bygg AS, 10000 kr"

**English:**
- "Pay supplier invoice 5001 by bank transfer"

### 6.4 Find Supplier (FIND_SUPPLIER)

**Norwegian:**
- "Finn alle leverandører med navn 'Oslo'"
- "Søk etter leverandør med org.nr 912345678"
- "Vis leverandørlisten"

**English:**
- "Find supplier with organization number 912345678"

### 6.5 Approve Supplier Invoice

**Norwegian:**
- "Godkjenn leverandørfaktura 1234"
- "Godkjenn alle ventende leverandørfakturaer"

### 6.6 Dimension/Cost Allocation

**Norwegian:**
- "Bokfør leverandørfaktura fra X på avdeling Salg"
- "Registrer faktura fra X på prosjekt P-2026-001"

---

## 7. Gap Analysis

### 7.1 CRITICAL: Missing voucherType

**Current code** (executor.py:2979-3005): Creates voucher WITHOUT setting `voucherType`.
**Result:** Vouchers are created with `voucherType: null` — they are generic journal entries, NOT supplier invoices. This means:
- They don't appear in `/supplierInvoice` queries
- They can't be approved via the supplier invoice approval workflow
- They can't be paid via `/supplierInvoice/:addPayment`
- They are essentially invisible to the supplier invoice management UI

**Fix:** Add `"voucherType": {"id": 10155922}` to the voucher payload.

### 7.2 CRITICAL: Vouchers Not Posted to Ledger

**Current code** (tripletex_client.py:492): `send_to_ledger=False` (default)
**Result:** Vouchers stay in "Ikke bokført" (not posted) state indefinitely.

**Fix:** Pass `send_to_ledger=True` when creating supplier invoice vouchers.

### 7.3 CRITICAL: Fallback to POST /supplierInvoice (doesn't exist)

**Current code** (executor.py:3019-3054): Falls back to `POST /supplierInvoice` which doesn't exist.
**Result:** Always fails with 404 or method not allowed.

**Fix:** Remove the fallback entirely. The voucher approach is the only correct one.

### 7.4 MODERATE: No VAT Handling

**Current code** (executor.py:2986-2989): Uses `amount` for both `amountGross` and regular `amount`.
**Issue:** Doesn't distinguish between amount including/excluding VAT. When the account has a VAT type (e.g., account 4300 has vatType=1 for 25% incoming VAT), the `amountGross` should be the VAT-inclusive amount so Tripletex can auto-calculate the VAT posting.

**Current behavior:** If user says "10000 kr inkl. mva", the amount field works correctly (amountGross=10000, Tripletex splits to 8000 + 2000 VAT). But if user says "10000 kr ekskl. mva", we'd need to compute amountGross=12500.

**Fix:** When `amount_excluding_vat` is provided, calculate gross = amount_excl × 1.25 for accounts with 25% VAT.

### 7.5 MODERATE: Supplier Name Search Doesn't Work

**Current code** (executor.py:2936): Uses `name` param on GET /supplier
**Issue:** GET /supplier does NOT have a `name` query parameter. The param is silently ignored, returning all suppliers. This means:
- `get_suppliers({"name": "Bygg AS"})` returns ALL suppliers
- Code takes `existing[0]` — gets wrong supplier!

**Fix:** Either:
1. Use `organizationNumber` for exact match (preferred)
2. Fetch all suppliers and filter client-side by name
3. Use `/supplierCustomer/search` endpoint (supports text search)

### 7.6 MINOR: No vendorInvoiceNumber

**Current code:** Doesn't set `vendorInvoiceNumber` on the voucher.
**Impact:** Can't track the supplier's invoice number for matching/reconciliation.

**Fix:** Add `"vendorInvoiceNumber": invoice_number` to the voucher payload.

### 7.7 MINOR: No Dimension Support

**Current code:** Doesn't support department/project allocation on supplier invoices.
**Impact:** Can't fulfill prompts like "Bokfør på avdeling Salg" or "Registrer på prosjekt X".

**Fix:** Add `department` and `project` fields to the debit posting when specified.

### 7.8 MINOR: No Supplier Invoice Payment Executor

**Current code:** No task type or executor for paying supplier invoices.
**Impact:** Can't fulfill "Betal leverandørfaktura" prompts.

**Fix:** Add `PAY_SUPPLIER_INVOICE` task type using `POST /supplierInvoice/{id}/:addPayment`.

---

## 8. Recommendations

### Priority 1 — Fix Supplier Invoice Creation (CRITICAL)

1. **Set voucherType** to `{"id": 10155922}` (Leverandørfaktura)
2. **Set sendToLedger=true** when creating the voucher
3. **Remove the POST /supplierInvoice fallback** — it doesn't exist
4. **Set vendorInvoiceNumber** from the extracted `invoice_number` field

**Corrected voucher payload:**
```python
voucher_payload = {
    "date": voucher_date,
    "description": description,
    "voucherType": {"id": 10155922},  # ← ADD THIS
    "vendorInvoiceNumber": invoice_number,  # ← ADD THIS
    "postings": [
        {
            "date": voucher_date,
            "description": description,
            "account": {"id": expense_acct_id},
            "amountGross": amount,
            "amountGrossCurrency": amount,
            "currency": {"id": 1},
            "row": 1,
        },
        {
            "date": voucher_date,
            "description": f"Leverandørgjeld {supplier_name}",
            "account": {"id": liability_acct_id},
            "supplier": {"id": supplier_id},
            "amountGross": -amount,
            "amountGrossCurrency": -amount,
            "currency": {"id": 1},
            "row": 2,
        },
    ],
}
# Create with sendToLedger=True
voucher = await client.create_voucher(voucher_payload, send_to_ledger=True)
```

### Priority 2 — Fix Supplier Search

Replace name-based search with client-side filtering:
```python
# Instead of: get_suppliers({"name": supplier_name})
all_suppliers = await client.get_suppliers({})
matches = [s for s in all_suppliers if supplier_name.lower() in s["name"].lower()]
if matches:
    supplier_id = matches[0]["id"]
```

Or use organizationNumber when available (always preferred):
```python
if org_number:
    results = await client.get_suppliers({"organizationNumber": org_number})
```

### Priority 3 — VAT Handling

Add VAT-aware amount calculation:
```python
# If amount_excluding_vat is given and account has VAT
if amount_excl_vat and not amount_incl_vat:
    vat_pct = get_account_vat_percentage(expense_acct_id)  # 25%, 15%, 12%, 0%
    amount_gross = amount_excl_vat * (1 + vat_pct / 100)
else:
    amount_gross = amount_incl_vat or amount_excl_vat or 0
```

### Priority 4 — Add Department/Project Dimensions

```python
# Add to debit posting when specified
debit_posting = {
    ...
    "department": {"id": dept_id} if dept_id else None,
    "project": {"id": project_id} if project_id else None,
}
```

### Priority 5 — Expand Task Types

Consider adding:
- `PAY_SUPPLIER_INVOICE` — POST /supplierInvoice/{id}/:addPayment
- `APPROVE_SUPPLIER_INVOICE` — PUT /supplierInvoice/{id}/:approve
- `REJECT_SUPPLIER_INVOICE` — PUT /supplierInvoice/{id}/:reject

### Account Number Selection Logic

Map common Norwegian expense categories to accounts:
```python
EXPENSE_ACCOUNT_MAP = {
    "varekjøp": 4300,      # Innkjøp av varer for videresalg
    "råvarer": 4000,        # Innkjøp av råvarer
    "kontorrekvisita": 6800, # Kontorrekvisita
    "leie": 6300,           # Leie lokale
    "it": 6810,             # Datakostnad
    "revisjon": 6701,       # Honorar revisjon
    "regnskap": 6705,       # Honorar regnskap
    "juridisk": 6725,       # Honorar juridisk bistand
    "frakt": 6100,          # Frakt og transport
    "strøm": 6200,          # Elektrisitet
    "reparasjon": 6620,     # Reparasjon og vedlikehold
    "drivstoff": 6250,      # Bensin, diesel
    "default": 4000,        # Default expense account
}
```
