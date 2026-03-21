from __future__ import annotations

"""Gemini-powered task classifier for the Tripletex AI Accounting Agent.

Classifies natural-language prompts (7 languages) into TaskType + extracted fields
using a single LLM call with structured JSON output.
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Optional

from task_types import (
    TASK_FIELD_SPECS,
    TASK_TYPE_DESCRIPTIONS,
    TaskClassification,
    TaskType,
)

logger = logging.getLogger("tripletex-agent.classifier")

# ---------------------------------------------------------------------------
# SDK import — try new unified SDK first, fall back to older one
# ---------------------------------------------------------------------------

_USE_NEW_SDK = True

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    _USE_NEW_SDK = False
    try:
        import google.generativeai as genai  # type: ignore[no-redef]
        genai_types = None  # older SDK lacks this module
    except ImportError:
        genai = None  # type: ignore[assignment]
        genai_types = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
TEMPERATURE = 0.0
MAX_RETRIES = 3

# Claude fallback — disable after first failure to avoid wasting round-trips
_claude_disabled = False

def _set_claude_disabled():
    global _claude_disabled
    _claude_disabled = True

# ---------------------------------------------------------------------------
# System prompt — comprehensive, multilingual, with few-shot examples
# ---------------------------------------------------------------------------


def _build_task_type_block() -> str:
    """Generate the task-type + field-spec section of the system prompt."""
    lines: list[str] = []
    for tt in TaskType:
        desc = TASK_TYPE_DESCRIPTIONS.get(tt, "")
        spec = TASK_FIELD_SPECS.get(tt, {})
        required = spec.get("required", [])
        optional = spec.get("optional", [])

        lines.append(f"### {tt.value}")
        lines.append(f"Description: {desc}")
        if required:
            lines.append(f"Required fields: {', '.join(required)}")
        if optional:
            lines.append(f"Optional fields: {', '.join(optional)}")
        lines_spec = spec.get("lines_fields")
        if lines_spec:
            lopt = lines_spec.get("optional", [])
            lines.append(f"Each item in 'lines' can have: {', '.join(lopt)}")
        lines.append("")
    return "\n".join(lines)


def _build_system_prompt() -> str:
    return f"""\
You are an accounting task classifier for Tripletex ERP (Norwegian cloud accounting software).

Given a task description in ANY of these languages — Norwegian Bokmål (nb), Nynorsk (nn), \
English (en), Spanish (es), Portuguese (pt), German (de), French (fr) — you must:
1. Identify the task_type (one of the values listed below).
2. Extract all relevant fields from the text.
3. Assign a confidence score (0.0–1.0).

## TASK TYPES AND FIELDS

{_build_task_type_block()}

## FIELD FORMATTING RULES
- ONLY extract fields explicitly stated in the prompt. NEVER fabricate emails, phones, addresses, or websites that are not present in the input text.
- Dates → YYYY-MM-DD (convert from any format: "15. mars 2026" → "2026-03-15")
- Numbers → plain decimals, no thousand separators ("1 200,50" → 1200.50)
- Currency amounts → assume NOK unless explicitly stated otherwise
- Names → preserve original casing exactly as written
- Booleans → true / false
- Phone numbers → preserve as-is (including country code if given)
- Organization numbers → digits only, no spaces
- VAT rates → extract as vat_percentage (plain number, e.g. 25, 15, 12, 0). Keywords: MVA, mva, MwSt, Steuersatz, tax rate, VAT, TVA, IVA, taux

## LANGUAGE-SPECIFIC KEYWORDS
| Concept | Bokmål (nb) | Nynorsk (nn) | English | Spanish | Portuguese | German | French |
|---------|-------------|--------------|---------|---------|------------|--------|--------|
| employee | ansatt | tilsett | employee | empleado | funcionário | Mitarbeiter | employé |
| customer | kunde | kunde | customer | cliente | cliente | Kunde | client |
| invoice | faktura | faktura | invoice | factura | fatura | Rechnung | facture |
| product | produkt | produkt | product | producto | produto | Produkt | produit |
| project | prosjekt | prosjekt | project | proyecto | projeto | Projekt | projet |
| department | avdeling | avdeling | department | departamento | departamento | Abteilung | département |
| travel expense | reiseregning | reiserekning | travel expense | gasto de viaje | despesa de viagem | Reisekostenabrechnung | note de frais |
| credit note | kreditnota | kreditnota | credit note | nota de crédito | nota de crédito | Gutschrift | avoir |
| payment | betaling/innbetaling | betaling | payment | pago | pagamento | Zahlung | paiement |
| contact | kontaktperson | kontaktperson | contact | contacto | contato | Kontakt | contact |
| dimension | dimensjon | dimensjon | dimension | dimensión | dimensão | Dimension/Buchhaltungsdimension | dimension |
| voucher/posting | bilag/postering | bilag/postering | voucher/posting | asiento | lançamento | Beleg/Buchung | écriture |
| delete | slett/fjern | slett/fjern | delete/remove | eliminar/borrar | excluir/remover | löschen/entfernen | supprimer |
| update | oppdater/endre | oppdater/endre | update/modify | actualizar/modificar | atualizar/modificar | aktualisieren/ändern | mettre à jour/modifier |

## IMPORTANT DISAMBIGUATION RULES
- "Opprett faktura" / "Create invoice" with a NEW customer name → create_invoice
- "Opprett faktura" / "Create invoice" referencing an EXISTING customer (by name/number) → invoice_existing_customer
- If the prompt says to create an invoice AND register payment → invoice_with_payment
- "Opprett ansatt" / "Create employee" → create_employee (NOT create_contact)
- "Opprett kontaktperson" / "Create contact" → create_contact
- "Slett" / "fjern" / "delete" / "remove" + employee → delete_employee
- "Endre" / "oppdater" / "update" / "modify" + employee → update_employee
- If unsure between create_invoice and invoice_existing_customer, prefer invoice_existing_customer \
when the prompt implies the customer already exists in the system.
- Travel expense keywords: "reiseregning", "reise", "diett", "kjøregodtgjørelse", "utlegg"
- leverandør/supplier + faktura/invoice → create_supplier_invoice (NOT create_invoice)
- "inngående faktura", "mottatt faktura", "leverandørfaktura", "Eingangsrechnung", "facture fournisseur" → create_supplier_invoice
- CRITICAL: "Registrieren Sie den Lieferanten" / "registrer leverandør" / "register supplier" → create_supplier (NOT create_customer)
- CRITICAL: "Exécutez la paie" / "kjør lønn" / "run payroll" / "Gehaltsabrechnung" / "ejecutar nómina" → run_payroll
- CRITICAL: "reverser betaling" / "payment returned/bounced by bank" / "Zahlung rückerstattet" → reverse_payment (NOT create_credit_note or error_correction). \
The goal is to reverse the payment voucher so the invoice is outstanding again.
- paie/salaire/lønn/Gehalt/nómina + employee name + amount → run_payroll (salary payment)
- Lieferant/leverandør/supplier WITHOUT faktura/invoice keywords → create_supplier (register the supplier entity)
- "oppdater produkt" / "endre produkt" / "update product" / "modify product" → update_product
- "slett produkt" / "fjern produkt" / "delete product" / "remove product" → delete_product
- "oppdater leverandør" / "endre leverandør" / "update supplier" → update_supplier
- "slett leverandør" / "fjern leverandør" / "delete supplier" → delete_supplier
- "finn leverandør" / "søk leverandør" / "find supplier" / "search supplier" → find_supplier
- "slett avdeling" / "fjern avdeling" / "delete department" → delete_department
- When a prompt mentions both creating a project AND linking it to a customer → project_with_customer
- "Legg til rolle" / "set role" / "set access" → set_employee_roles
- CRITICAL: If the prompt describes a customer with an unpaid invoice and asks to register payment, \
this is invoice_with_payment (create customer + invoice + payment in one flow), NOT register_payment. \
register_payment is ONLY for registering payment on an ALREADY EXISTING invoice in the system.
- "facture impayée" / "unbezahlte Rechnung" / "unpaid invoice" + customer details → invoice_with_payment
- If the prompt gives customer details (name, org number) AND invoice details (amount, description) \
AND mentions payment → invoice_with_payment
- dimension/Buchhaltungsdimension/dimensjon + values/voucher/Beleg → create_dimension_voucher
- "fri dimensjon", "custom dimension", "Kostsenter", "Kostenstelle", "cost center" → create_dimension_voucher

## FEW-SHOT EXAMPLES

### Example 1 — Create employee (Bokmål)
Input: "Opprett en ansatt med navn Ola Nordmann, e-post ola@example.com"
Output:
{{"task_type": "create_employee", "confidence": 0.98, "fields": {{"first_name": "Ola", "last_name": "Nordmann", "email": "ola@example.com"}}}}

### Example 2 — Create employee (Nynorsk)
Input: "Opprett ein tilsett med namn Kari Nordmann"
Output:
{{"task_type": "create_employee", "confidence": 0.95, "fields": {{"first_name": "Kari", "last_name": "Nordmann"}}}}

### Example 3 — Create employee (English)
Input: "Create an employee named John Smith with email john@smith.com, phone +47 912 34 567, starting March 1st 2026"
Output:
{{"task_type": "create_employee", "confidence": 0.99, "fields": {{"first_name": "John", "last_name": "Smith", "email": "john@smith.com", "phone": "+47 912 34 567"}}}}

### Example 4 — Create customer (German)
Input: "Erstellen Sie einen Kunden namens Schmidt GmbH mit der Organisationsnummer 123456789"
Output:
{{"task_type": "create_customer", "confidence": 0.97, "fields": {{"name": "Schmidt GmbH", "organization_number": "123456789"}}}}

### Example 5 — Create customer (Bokmål)
Input: "Opprett kunde Fjord Konsult AS med org.nr 987654321, e-post post@fjord.no, adresse Storgata 5, 0001 Oslo"
Output:
{{"task_type": "create_customer", "confidence": 0.98, "fields": {{"name": "Fjord Konsult AS", "organization_number": "987654321", "email": "post@fjord.no", "address_line1": "Storgata 5", "postal_code": "0001", "city": "Oslo"}}}}

### Example 6 — Create invoice (Spanish)
Input: "Crear una factura para el cliente Empresa SA por 2 unidades de Producto X a 500 NOK cada una"
Output:
{{"task_type": "create_invoice", "confidence": 0.95, "fields": {{"customer_name": "Empresa SA", "lines": [{{"product_name": "Producto X", "quantity": 2, "unit_price": 500.0}}]}}}}

### Example 6b — Invoice existing customer with product numbers (Spanish)
Input: "Crea una factura para el cliente Sierra SL (org. nº 832052582) con tres líneas de producto: Sesión de formación (6481) a 3200 NOK, Licencia de software (7892) a 15000 NOK, y Soporte técnico (3310) a 4500 NOK"
Output:
{{"task_type": "invoice_existing_customer", "confidence": 0.97, "fields": {{"customer_identifier": "Sierra SL", "organization_number": "832052582", "lines": [{{"product_name": "Sesión de formación", "number": "6481", "quantity": 1, "unit_price": 3200.0}}, {{"product_name": "Licencia de software", "number": "7892", "quantity": 1, "unit_price": 15000.0}}, {{"product_name": "Soporte técnico", "number": "3310", "quantity": 1, "unit_price": 4500.0}}]}}}}

### Example 6c — Invoice with multiple product lines (Bokmål)
Input: "Lag faktura til kunde Hansen AS: 3 stk Frakttjeneste til 2500 kr og 1 stk Emballasje til 150 kr"
Output:
{{"task_type": "create_invoice", "confidence": 0.95, "fields": {{"customer_name": "Hansen AS", "lines": [{{"description": "Frakttjeneste", "quantity": 3, "unit_price": 2500.0}}, {{"description": "Emballasje", "quantity": 1, "unit_price": 150.0}}]}}}}

### Example 7 — Create invoice (Bokmål)
Input: "Opprett en faktura til kunde Acme AS for 10 timer konsulentarbeid à 1200 kr"
Output:
{{"task_type": "create_invoice", "confidence": 0.96, "fields": {{"customer_name": "Acme AS", "lines": [{{"description": "Konsulentarbeid", "quantity": 10, "unit_price": 1200.0}}]}}}}

### Example 8 — Create department (French)
Input: "Créer un département appelé Marketing"
Output:
{{"task_type": "create_department", "confidence": 0.98, "fields": {{"name": "Marketing"}}}}

### Example 9 — Create project (Portuguese)
Input: "Criar um projeto chamado Website Redesign para o cliente ABC Corp, início em 01/04/2026"
Output:
{{"task_type": "create_project", "confidence": 0.96, "fields": {{"name": "Website Redesign", "customer_name": "ABC Corp", "start_date": "2026-04-01"}}}}

### Example 10 — Create product (English)
Input: "Create a product called 'Premium Support' with price 2500 NOK excluding VAT"
Output:
{{"task_type": "create_product", "confidence": 0.97, "fields": {{"name": "Premium Support", "price_excluding_vat": 2500.0}}}}

### Example 10b — Create product with VAT rate (German)
Input: "Erstellen Sie das Produkt 'Datenberatung' mit der Produktnummer 5524. Der Preis beträgt 22550 NOK ohne MwSt., mit dem Steuersatz 25%"
Output:
{{"task_type": "create_product", "confidence": 0.98, "fields": {{"name": "Datenberatung", "number": "5524", "price_excluding_vat": 22550.0, "vat_percentage": 25}}}}

### Example 10c — Create product with VAT (Norwegian)
Input: "Opprett produkt Konsulenttjeneste med pris 1500 kr eks. mva, 25% MVA"
Output:
{{"task_type": "create_product", "confidence": 0.97, "fields": {{"name": "Konsulenttjeneste", "price_excluding_vat": 1500.0, "vat_percentage": 25}}}}

### Example 11 — Register payment (Bokmål)
Input: "Registrer innbetaling på faktura 10042 med beløp 15000 kr, dato 15.03.2026"
Output:
{{"task_type": "register_payment", "confidence": 0.97, "fields": {{"invoice_identifier": "10042", "amount": 15000.0, "payment_date": "2026-03-15"}}}}

### Example 12 — Create travel expense (Bokmål)
Input: "Opprett reiseregning for ansatt Per Hansen, dagsreise fra Bergen til Oslo 19. mars 2026, formål: kundemøte"
Output:
{{"task_type": "create_travel_expense", "confidence": 0.96, "fields": {{"employee_identifier": "Per Hansen", "departure_from": "Bergen", "destination": "Oslo", "departure_date": "2026-03-19", "return_date": "2026-03-19", "is_day_trip": true, "purpose": "kundemøte"}}}}

### Example 13 — Create contact (English)
Input: "Add a contact person for customer Acme AS: Jane Doe, jane@acme.no, mobile 99887766"
Output:
{{"task_type": "create_contact", "confidence": 0.97, "fields": {{"first_name": "Jane", "last_name": "Doe", "customer_identifier": "Acme AS", "email": "jane@acme.no", "phone": "99887766"}}}}

### Example 14 — Delete employee (Bokmål)
Input: "Slett ansatt Ola Nordmann"
Output:
{{"task_type": "delete_employee", "confidence": 0.96, "fields": {{"employee_identifier": "Ola Nordmann"}}}}

### Example 15 — Update customer (English)
Input: "Update the email for customer Nordic Tech AS to info@nordictech.no"
Output:
{{"task_type": "update_customer", "confidence": 0.95, "fields": {{"customer_identifier": "Nordic Tech AS", "email": "info@nordictech.no"}}}}

### Example 16 — Credit note (Bokmål)
Input: "Opprett kreditnota for faktura 10055"
Output:
{{"task_type": "create_credit_note", "confidence": 0.97, "fields": {{"invoice_identifier": "10055"}}}}

### Example 17 — Project with customer (Bokmål)
Input: "Opprett prosjekt 'Nettside' for kunde Digitalbyrå AS, start 01.04.2026, fast pris 50000 kr"
Output:
{{"task_type": "project_with_customer", "confidence": 0.96, "fields": {{"project_name": "Nettside", "customer_identifier": "Digitalbyrå AS", "start_date": "2026-04-01", "is_fixed_price": true, "fixed_price": 50000.0}}}}

### Example 18 — Invoice with payment (English)
Input: "Create an invoice for Acme Corp for 3 hours consulting at 1500 NOK/hr, already paid in full"
Output:
{{"task_type": "invoice_with_payment", "confidence": 0.95, "fields": {{"customer_name": "Acme Corp", "lines": [{{"description": "Consulting", "quantity": 3, "unit_price": 1500.0}}], "paid_amount": 4500.0}}}}

### Example 18b — Invoice with payment (French — unpaid invoice scenario)
Input: "Le client Colline SARL (nº org. 850491941) a une facture impayée de 10550 NOK hors TVA pour \"Heures de conseil\". Enregistrer le paiement de cette facture."
Output:
{{"task_type": "invoice_with_payment", "confidence": 0.97, "fields": {{"customer_name": "Colline SARL", "organization_number": "850491941", "lines": [{{"description": "Heures de conseil", "quantity": 1, "unit_price": 10550.0}}], "paid_amount": 10550.0}}}}

### Example 18c — Invoice with payment (German)
Input: "Der Kunde Müller GmbH (Org.Nr. 912345678) hat eine unbezahlte Rechnung über 5000 NOK für Beratung. Zahlung registrieren."
Output:
{{"task_type": "invoice_with_payment", "confidence": 0.97, "fields": {{"customer_name": "Müller GmbH", "organization_number": "912345678", "lines": [{{"description": "Beratung", "quantity": 1, "unit_price": 5000.0}}], "paid_amount": 5000.0}}}}

### Example 19 — Find customer (Bokmål)
Input: "Finn kunde med org.nr 912345678"
Output:
{{"task_type": "find_customer", "confidence": 0.96, "fields": {{"search_query": "912345678", "search_field": "organization_number"}}}}

### Example 19b — Supplier invoice (Nynorsk)
Input: "Me har motteke faktura frå leverandøren Vestfjord AS (org.nr 923456789) på 45000 kr inkl. mva for konsulenttjenester"
Output:
{{"task_type": "create_supplier_invoice", "confidence": 0.97, "fields": {{"supplier_name": "Vestfjord AS", "organization_number": "923456789", "amount_including_vat": 45000.0, "description": "konsulenttjenester"}}}}

### Example 20 — Set employee roles (English)
Input: "Set employee John Doe as a standard user with no access"
Output:
{{"task_type": "set_employee_roles", "confidence": 0.94, "fields": {{"employee_identifier": "John Doe", "user_type": "NO_ACCESS"}}}}

### Example 22 — Create dimension + voucher (German)
Input: "Erstellen Sie eine benutzerdefinierte Buchhaltungsdimension 'Kostsenter' mit den Werten 'IT' und 'Innkjøp'. Buchen Sie dann einen Beleg auf Konto 7000 über 19450 NOK, verknüpft mit dem Dimensionswert 'IT'."
Output:
{{"task_type": "create_dimension_voucher", "confidence": 0.97, "fields": {{"dimension_name": "Kostsenter", "dimension_values": ["IT", "Innkjøp"], "account_number": "7000", "amount": 19450.0, "linked_dimension_value": "IT"}}}}

### Example 22b — Create dimension (Norwegian)
Input: "Opprett en fri dimensjon 'Kostsenter' med verdiene 'Salg' og 'Drift', og bokfør et bilag på konto 6000 for 5000 NOK knyttet til 'Salg'"
Output:
{{"task_type": "create_dimension_voucher", "confidence": 0.96, "fields": {{"dimension_name": "Kostsenter", "dimension_values": ["Salg", "Drift"], "account_number": "6000", "amount": 5000.0, "linked_dimension_value": "Salg"}}}}

### Example 23 — Register supplier (German)
Input: "Registrieren Sie den Lieferanten Nordlicht GmbH mit der Organisationsnummer 922976457. E-Mail: faktura@nordlichtgmbh.no."
Output:
{{"task_type": "create_supplier", "confidence": 0.97, "fields": {{"name": "Nordlicht GmbH", "organization_number": "922976457", "email": "faktura@nordlichtgmbh.no"}}}}

### Example 23b — Register supplier (Norwegian)
Input: "Registrer leverandøren Havbris AS med org.nr. 987654321 og e-post: post@havbris.no"
Output:
{{"task_type": "create_supplier", "confidence": 0.96, "fields": {{"name": "Havbris AS", "organization_number": "987654321", "email": "post@havbris.no"}}}}

### Example 24 — Run payroll (French)
Input: "Exécutez la paie de Jules Leroy (jules.leroy@example.org) pour ce mois. Le salaire de base est de 56950 NOK. Ajoutez une prime unique de 9350 NOK en plus du salaire de base."
Output:
{{"task_type": "run_payroll", "confidence": 0.97, "fields": {{"employee_identifier": "Jules Leroy", "first_name": "Jules", "last_name": "Leroy", "email": "jules.leroy@example.org", "base_salary": 56950.0, "bonus": 9350.0}}}}

### Example 24b — Run payroll (Norwegian)
Input: "Kjør lønn for ansatt Kari Hansen (kari@example.no) for mars 2026. Grunnlønn 45000 NOK."
Output:
{{"task_type": "run_payroll", "confidence": 0.96, "fields": {{"employee_identifier": "Kari Hansen", "first_name": "Kari", "last_name": "Hansen", "email": "kari@example.no", "base_salary": 45000.0, "month": "03", "year": "2026"}}}}

### Example 25 — Payment returned / bounced (Portuguese)
Input: "O pagamento de Cascata Lda (org. nº 844279892) referente à fatura 'Horas de consultoria' (41350 NOK sem IVA) foi devolvido pelo banco. Reverta o pagamento para reabrir a fatura."
Output:
{{"task_type": "reverse_payment", "confidence": 0.97, "fields": {{"customer_name": "Cascata Lda", "organization_number": "844279892"}}}}

### Example 25b — Reverse payment (Norwegian)
Input: "Betalingen fra Tindra AS ble returnert av banken. Reverser betalingen slik at fakturaen igjen vises som utestående."
Output:
{{"task_type": "reverse_payment", "confidence": 0.97, "fields": {{"customer_name": "Tindra AS"}}}}

## BATCH OPERATIONS
If the prompt asks to create MULTIPLE entities of the same type (e.g., "Create three departments: X, Y, Z"),
return a JSON object with a "batch" array containing one classification per entity:
{{"batch": [{{"task_type": "create_department", "confidence": 0.98, "fields": {{"name": "X"}}}}, {{"task_type": "create_department", "confidence": 0.98, "fields": {{"name": "Y"}}}}, ...]}}

### Example 21 — Batch departments
Input: "Create three departments in Tripletex: Utvikling, Innkjøp, and Salg."
Output:
{{"batch": [{{"task_type": "create_department", "confidence": 0.98, "fields": {{"name": "Utvikling"}}}}, {{"task_type": "create_department", "confidence": 0.98, "fields": {{"name": "Innkjøp"}}}}, {{"task_type": "create_department", "confidence": 0.98, "fields": {{"name": "Salg"}}}}]}}

## EMPLOYEE USER TYPE / ROLE
When the prompt mentions administrator, admin, kontoadministrator → set user_type to "ADMINISTRATOR"
When the prompt mentions standard → set user_type to "STANDARD"
When the prompt mentions begrenset/limited/restricted → set user_type to "RESTRICTED"
When the prompt mentions ingen tilgang/no access → set user_type to "NO_ACCESS"

## OUTPUT FORMAT
Respond with ONLY a JSON object (no markdown, no explanation) with exactly these keys:
- task_type: string (one of the task type values listed above)
- confidence: number between 0.0 and 1.0
- fields: object with the extracted field values

For batch operations, use the batch format described above.

If you cannot determine the task type, use "unknown" with confidence 0.0 and empty fields.
"""


SYSTEM_PROMPT = _build_system_prompt()


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------


def _build_client():
    """Create a Gemini client based on available SDK and env vars."""
    gcp_project = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if _USE_NEW_SDK:
        if api_key:
            # Prefer API key — works everywhere, no Vertex AI region issues
            return genai.Client(api_key=api_key)
        elif gcp_project:
            return genai.Client(
                vertexai=True,
                project=gcp_project,
                location=os.environ.get("GCP_REGION", "europe-north1"),
            )
        else:
            # Default: try Vertex AI with Application Default Credentials (Cloud Run)
            return genai.Client(vertexai=True)
    else:
        # Older google-generativeai SDK
        if api_key:
            genai.configure(api_key=api_key)
        return genai


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = _build_client()
    return _client


# ---------------------------------------------------------------------------
# Claude-based classifier (fallback when Gemini unavailable)
# ---------------------------------------------------------------------------

_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


_CLAUDE_SYSTEM = SYSTEM_PROMPT


async def _classify_with_claude(
    prompt: str,
    files: Optional[list[dict]] = None,
) -> TaskClassification:
    """Classify using Anthropic Claude API."""
    loop = asyncio.get_running_loop()
    client = _get_anthropic_client()

    user_message = prompt
    if files:
        file_names = [f.get("name", f.get("filename", "unnamed")) for f in files]
        user_message += f"\n\n[Attached files: {', '.join(file_names)}]"

    def _sync():
        return client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=1024,
            temperature=0.0,
            system=_CLAUDE_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )

    response = await loop.run_in_executor(None, _sync)
    raw_text = response.content[0].text.strip()

    return _parse_response(raw_text, prompt)


# ---------------------------------------------------------------------------
# Core classification function
# ---------------------------------------------------------------------------


async def classify_task(
    prompt: str,
    files: Optional[list[dict]] = None,
) -> TaskClassification:
    """Classify a natural-language task prompt into a TaskType with extracted fields.

    Three modes, checked in order:
      1. Gemini (if GEMINI_MODEL env var set / google-genai SDK available)
      2. Claude (if ANTHROPIC_API_KEY env var set)
      3. Rule-based keyword matching (always available)

    Args:
        prompt: The task description in any of the 7 supported languages.
        files: Optional list of file dicts (with 'name'/'filename', 'mime_type' keys).

    Returns:
        TaskClassification with task_type, confidence, fields, and raw_prompt.
    """
    def _post_process_result(r):
        r.fields = _post_process_fields(r.task_type, r.fields)
        r.fields = _strip_hallucinated_fields(r.fields, prompt)
        return r

    def _post_process_any(r):
        if isinstance(r, list):
            return [_post_process_result(item) for item in r]
        return _post_process_result(r)

    # --- Try Gemini first ---
    if genai is not None and os.environ.get("GEMINI_MODEL"):
        try:
            result = await _classify_with_gemini(prompt, files)
            # Batch result — return list directly
            if isinstance(result, list):
                return _post_process_any(result)
            if result.task_type != TaskType.UNKNOWN or result.confidence > 0.5:
                return _post_process_result(result)
            logger.info("Gemini returned UNKNOWN, trying next fallback")
        except Exception as e:
            logger.warning("Gemini classification failed: %s — trying next fallback", e)

    # --- Try Claude second (skip if previously failed) ---
    if os.environ.get("ANTHROPIC_API_KEY") and not _claude_disabled:
        try:
            result = await _classify_with_claude(prompt, files)
            if result.task_type != TaskType.UNKNOWN or result.confidence > 0.5:
                return _post_process_result(result)
            logger.info("Claude returned UNKNOWN, trying keyword fallback")
        except Exception as e:
            logger.warning("Claude classification failed: %s — disabling Claude fallback", e)
            _set_claude_disabled()

    # --- Keyword fallback (always available) ---
    result = _classify_with_keywords(prompt, files)
    if result.task_type != TaskType.UNKNOWN:
        return _post_process_result(result)

    # --- Last-resort single-word heuristic — NEVER return UNKNOWN if any signal exists ---
    result = _last_resort_classify(prompt)
    if result.task_type != TaskType.UNKNOWN:
        logger.warning("Last-resort heuristic matched: %s for prompt: %s", result.task_type.value, prompt[:100])
    else:
        logger.error("ALL classifiers returned UNKNOWN — prompt: %s", prompt[:200])
    return _post_process_result(result)


async def _classify_with_gemini(
    prompt: str,
    files: Optional[list[dict]] = None,
) -> TaskClassification | list[TaskClassification]:
    """Classify using Gemini LLM with retry. May return a list for batch operations."""
    import base64
    client = _get_client()

    # Build multimodal content parts for Gemini
    content_parts = [prompt]
    if files:
        for f in files:
            b64 = f.get("content_base64", "")
            mime = f.get("mime_type", "application/octet-stream")
            fname = f.get("filename", f.get("name", "unnamed"))
            if b64 and _USE_NEW_SDK and genai_types:
                try:
                    raw_bytes = base64.b64decode(b64)
                    content_parts.append(genai_types.Part.from_bytes(
                        data=raw_bytes,
                        mime_type=mime,
                    ))
                    logger.info("Attached file %s (%s, %d bytes)", fname, mime, len(raw_bytes))
                except Exception as e:
                    logger.warning("Failed to decode file %s: %s", fname, e)
                    content_parts.append(f"\n[Attached file: {fname} ({mime}) — could not decode]")
            else:
                content_parts.append(f"\n[Attached file: {fname} ({mime})]")

    for attempt in range(1 + MAX_RETRIES):
        try:
            raw_text = await _call_gemini(client, content_parts)
            result = _parse_response(raw_text, prompt)
            # _parse_response may return a list for batch operations
            if isinstance(result, list):
                return result
            # If Gemini returned UNKNOWN on first try, retry before giving up
            if result.task_type == TaskType.UNKNOWN and attempt < MAX_RETRIES:
                logger.warning("Gemini returned UNKNOWN (attempt %d), retrying...", attempt + 1)
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            return result
        except Exception as e:
            logger.warning("Gemini attempt %d failed: %s", attempt + 1, e)
            if attempt >= MAX_RETRIES:
                raise
            await asyncio.sleep(0.5 * (2 ** attempt))

    raise RuntimeError("Gemini classification exhausted retries")


# ---------------------------------------------------------------------------
# Gemini call — handles both SDK variants, runs sync call in thread pool
# ---------------------------------------------------------------------------


async def _call_gemini(client: Any, user_message: str | list) -> str:
    """Call Gemini and return the raw response text."""
    loop = asyncio.get_running_loop()

    if _USE_NEW_SDK:

        def _sync():
            config_kwargs = dict(
                system_instruction=SYSTEM_PROMPT,
                temperature=TEMPERATURE,
                response_mime_type="application/json",
            )
            # gemini-2.5-pro requires thinking mode — use generous budget for best accuracy
            if "2.5-pro" in MODEL_NAME:
                config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                    thinking_budget=8192,
                )
            resp = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_message,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )
            return resp.text

    else:
        # Older google.generativeai SDK
        def _sync():
            model = client.GenerativeModel(
                MODEL_NAME,
                system_instruction=SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(  # type: ignore[attr-defined]
                    temperature=TEMPERATURE,
                    response_mime_type="application/json",
                ),
            )
            return model.generate_content(user_message).text

    return await loop.run_in_executor(None, _sync)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _post_process_fields(task_type: TaskType, fields: dict) -> dict:
    """Clean up extracted fields — safety net for both LLM and keyword paths.

    Strips name prefixes, email/phone suffixes, price text, and number text
    that LLMs sometimes include in name fields.
    """
    f = dict(fields)

    # --- Strip name prefixes from all name-type fields ---
    _name_prefix_words = [
        "named", "called", "med navn", "med navnet", "med namn",
        "namens", "genannt", "mit dem namen",
        "appelé", "appelée", "nommé", "nommée", "avec le nom",
        "llamado", "llamada", "con nombre", "denominado",
        "chamado", "chamada", "com nome",
        "heter", "heiter", "kalt",
        "som heter", "som heiter",
    ]
    name_fields = ["name", "first_name", "last_name", "department_name",
                    "customer_name", "project_name", "new_name"]
    for key in name_fields:
        val = f.get(key)
        if not val or not isinstance(val, str):
            continue
        cleaned = val.strip()
        lower = cleaned.lower()
        # Strip if the value starts with a prefix word (followed by space or is the entire value)
        for prefix in sorted(_name_prefix_words, key=len, reverse=True):
            if lower == prefix:
                # Entire value is a prefix word — clear it
                cleaned = ""
                break
            if lower.startswith(prefix + " "):
                cleaned = cleaned[len(prefix):].strip()
                lower = cleaned.lower()
                break
        if cleaned:
            f[key] = cleaned
        else:
            # Don't store empty strings — let executor handle missing fields
            f.pop(key, None)

    # --- Strip "with email X" / "med e-post X" etc. from name fields ---
    _email_suffix_re = re.compile(
        r'\s+(?:with\s+email|med\s+e-?post|og\s+e-?post|and\s+email|'
        r'mit\s+e-?mail|avec\s+e-?mail|con\s+(?:correo|email)|com\s+e-?mail)'
        r'\s+\S+.*$',
        re.IGNORECASE,
    )
    _phone_suffix_re = re.compile(
        r'\s+(?:with\s+phone|med\s+telefon|og\s+telefon|and\s+phone|'
        r'mit\s+telefon|avec\s+téléphone|con\s+teléfono|com\s+telefone)'
        r'\s+\S+.*$',
        re.IGNORECASE,
    )
    for key in ["name", "customer_name", "project_name"]:
        val = f.get(key)
        if not val or not isinstance(val, str):
            continue
        val = _email_suffix_re.sub("", val).strip()
        val = _phone_suffix_re.sub("", val).strip()
        f[key] = val

    # --- Strip price text from product names ---
    if task_type == TaskType.CREATE_PRODUCT:
        val = f.get("name")
        if val and isinstance(val, str):
            f["name"] = re.sub(
                r'\s+(?:til|at|for|zu|à|priced\s+at|costing|por)\s+\d[\d\s,.]*'
                r'(?:kr|NOK|nok|EUR|eur|USD|usd)?.*$',
                "", val, flags=re.IGNORECASE,
            ).strip()

    # --- Strip number text from department names ---
    if task_type == TaskType.CREATE_DEPARTMENT:
        val = f.get("name")
        if val and isinstance(val, str):
            f["name"] = re.sub(
                r'\s+(?:with\s+number|med\s+nummer|og\s+(?:avdelings)?nummer|'
                r'mit\s+nummer|avec\s+numéro|con\s+número|com\s+número|'
                r'numéro|número|nummer|number|nr\.?)'
                r'\s+\d+.*$',
                "", val, flags=re.IGNORECASE,
            ).strip()

    # --- Strip trailing connectors ---
    for key in name_fields:
        val = f.get(key)
        if not val or not isinstance(val, str):
            continue
        f[key] = val.rstrip(".,;:")

    return f


def _normalize_fields(task_type: TaskType, fields: dict) -> dict:
    """Normalize classifier output fields to match what executor.py expects.

    The LLM outputs generic identifiers (employee_identifier, customer_identifier, etc.)
    but the executor looks for specific sub-fields (first_name, last_name, customer_name, etc.).
    """
    f = dict(fields)  # shallow copy

    # --- Employee identifier → first_name / last_name ---
    emp_id = f.pop("employee_identifier", None)
    if emp_id and isinstance(emp_id, str):
        if emp_id.strip().isdigit():
            f.setdefault("employee_number", emp_id.strip())
        else:
            parts = emp_id.strip().split(None, 1)
            if len(parts) >= 2:
                f.setdefault("first_name", parts[0])
                f.setdefault("last_name", parts[1])
            elif len(parts) == 1:
                f.setdefault("last_name", parts[0])

    # --- Customer identifier → customer_name / name ---
    cust_id = f.pop("customer_identifier", None)
    if cust_id and isinstance(cust_id, str):
        f.setdefault("customer_name", cust_id)
        f.setdefault("name", cust_id)

    # --- Invoice identifier → invoice_number ---
    inv_id = f.pop("invoice_identifier", None)
    if inv_id is not None:
        f.setdefault("invoice_number", str(inv_id).strip())

    # --- Project identifier → project_name / project_id ---
    proj_id = f.pop("project_identifier", None)
    if proj_id is not None:
        proj_str = str(proj_id).strip()
        if proj_str.isdigit():
            f.setdefault("project_id", int(proj_str))
        else:
            f.setdefault("project_name", proj_str)

    # --- Travel expense identifier → travel_expense_id / title ---
    te_id = f.pop("travel_expense_identifier", None)
    if te_id is not None:
        te_str = str(te_id).strip()
        if te_str.isdigit():
            f.setdefault("travel_expense_id", int(te_str))
        else:
            f.setdefault("title", te_str)

    # --- Organization number: strip non-digit characters ---
    org = f.get("organization_number")
    if org and isinstance(org, str):
        f["organization_number"] = re.sub(r'[^0-9]', '', org)
    org2 = f.get("org_number")
    if org2 and isinstance(org2, str):
        f["org_number"] = re.sub(r'[^0-9]', '', org2)

    # --- find_customer: search_query → name/org_number/email for executor ---
    if task_type == TaskType.FIND_CUSTOMER:
        sq = f.get("search_query")
        sf = f.get("search_field", "name")
        if sq:
            if sf == "organization_number":
                f.setdefault("org_number", sq)
            elif sf == "email":
                f.setdefault("email", sq)
            else:
                f.setdefault("name", sq)

    # --- project_with_customer: project_name → name for create_project ---
    if task_type == TaskType.PROJECT_WITH_CUSTOMER:
        pn = f.get("project_name")
        if pn:
            f.setdefault("name", pn)

    return f


def _strip_hallucinated_fields(fields: dict, original_prompt: str) -> dict:
    """Remove email, phone, website fields whose values don't appear in the original prompt.

    LLMs sometimes fabricate contact info that isn't in the input text.
    """
    f = dict(fields)
    prompt_lower = original_prompt.lower()
    for key in ("email", "phone", "website"):
        val = f.get(key)
        if val and isinstance(val, str) and val.lower() not in prompt_lower:
            logger.info("Stripping hallucinated %s: %s", key, val)
            f.pop(key)
    return f


def _parse_single(data: dict, original_prompt: str) -> TaskClassification:
    """Parse a single classification dict into TaskClassification."""
    if not isinstance(data, dict):
        data = {}

    task_type_str = data.get("task_type", "unknown")
    try:
        task_type = TaskType(task_type_str)
    except ValueError:
        logger.warning("Unknown task_type from LLM: %s", task_type_str)
        task_type = TaskType.UNKNOWN

    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))

    fields = data.get("fields", {})
    if not isinstance(fields, dict):
        fields = {}

    fields = _normalize_fields(task_type, fields)
    fields = _strip_hallucinated_fields(fields, original_prompt)

    return TaskClassification(
        task_type=task_type,
        confidence=confidence,
        fields=fields,
        raw_prompt=original_prompt,
    )


def _parse_response(raw_text: str, original_prompt: str) -> TaskClassification | list[TaskClassification]:
    """Parse the JSON response from Gemini into TaskClassification(s).

    Returns a single TaskClassification or a list for batch operations.
    """
    text = raw_text.strip()

    # Strip markdown code fences if Gemini wraps the output
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON response: %s — raw text: %s", e, text[:500])
        raise ValueError(f"Malformed JSON from LLM: {e}") from e

    # Handle batch response: {"batch": [{...}, {...}, ...]}
    if isinstance(data, dict) and "batch" in data and isinstance(data["batch"], list):
        results = [_parse_single(item, original_prompt) for item in data["batch"] if item]
        return results if results else _parse_single({}, original_prompt)

    # Handle Gemini returning a list instead of a dict
    if isinstance(data, list) and len(data) > 1:
        # Multiple items — treat as batch
        results = [_parse_single(item, original_prompt) for item in data if isinstance(item, dict)]
        return results if results else _parse_single({}, original_prompt)
    elif isinstance(data, list):
        data = data[0] if data else {}

    return _parse_single(data, original_prompt)


# ---------------------------------------------------------------------------
# Keyword-based fallback classifier (no LLM required)
# ---------------------------------------------------------------------------

# Multilingual keyword patterns per task type.
# Each entry: list of keyword phrases (matched against lowercased prompt).
# "anti_keywords" prevent false positives (e.g., "delete employee" shouldn't match "create employee").

_TASK_PATTERNS: dict[TaskType, dict] = {
    TaskType.DELETE_EMPLOYEE: {
        "keywords": [
            "slett ansatt", "fjern ansatt", "delete employee", "remove employee",
            "eliminar empleado", "löschen mitarbeiter", "supprimer employé",
            "excluir funcionário", "slett tilsett", "fjern tilsett",
            # Swedish / Danish / Dutch / Finnish
            "ta bort anställd", "radera anställd", "slet medarbejder", "fjern medarbejder",
            "verwijder medewerker", "poista työntekijä",
        ],
    },
    TaskType.UPDATE_EMPLOYEE: {
        "keywords": [
            "oppdater ansatt", "endre ansatt", "update employee", "modify employee",
            "change employee", "edit employee", "rediger ansatt",
            "actualizar empleado", "modifier employé", "ändern mitarbeiter",
            "atualizar funcionário", "oppdater tilsett", "endre tilsett",
            # Swedish / Danish / Dutch / Finnish
            "uppdatera anställd", "ändra anställd", "opdater medarbejder", "ændr medarbejder",
            "wijzig medewerker", "päivitä työntekijä", "muokkaa työntekijä",
        ],
    },
    TaskType.SET_EMPLOYEE_ROLES: {
        "keywords": [
            "sett rolle", "set role", "set access", "endre rolle", "endre tilgang",
            "change role", "legg til rolle", "user type", "brukertype",
            "set employee role", "gi tilgang",
        ],
    },
    TaskType.CREATE_EMPLOYEE: {
        "keywords": [
            "opprett ansatt", "opprett en ansatt", "opprett ein ansatt",
            "ny ansatt", "create employee", "create an employee", "new employee",
            "add employee", "legg til ansatt", "registrer ansatt", "register employee",
            "crear empleado", "crear un empleado",
            "erstellen mitarbeiter", "einen mitarbeiter",
            "créer employé", "créer un employé",
            "criar funcionário", "criar um funcionário",
            "opprett tilsett", "opprett ein tilsett", "ny tilsett",
            "legg til tilsett",
            # Swedish / Danish / Dutch / Finnish
            "skapa anställd", "ny anställd", "opret medarbejder", "ny medarbejder",
            "maak medewerker", "nieuwe medewerker", "luo työntekijä", "uusi työntekijä",
        ],
        "anti_keywords": ["slett", "delete", "fjern", "remove", "oppdater", "update", "endre", "change", "rolle", "role", "tilgang"],
    },
    TaskType.UPDATE_CUSTOMER: {
        "keywords": [
            "oppdater kunde", "endre kunde", "update customer", "modify customer",
            "change customer", "edit customer", "rediger kunde",
            "actualizar cliente", "modifier client", "ändern kunde",
            # Swedish / Danish / Dutch / Finnish
            "uppdatera kund", "ändra kund", "opdater kunde", "ændr kunde",
            "wijzig klant", "päivitä asiakas",
        ],
    },
    TaskType.CREATE_CUSTOMER: {
        "keywords": [
            "opprett kunde", "opprett en kunde", "opprett ein kunde",
            "ny kunde", "create customer",
            "create a customer", "new customer", "add customer", "legg til kunde",
            "registrer kunde", "register customer",
            "crear cliente", "crear un cliente",
            "erstellen kunde", "erstellen sie einen kunden", "einen kunden",
            "créer client", "créer un client",
            "criar cliente", "criar um cliente", "neuer kunde",
            # Swedish / Danish / Dutch / Finnish
            "skapa kund", "ny kund", "opret kunde", "ny kunde",
            "maak klant", "nieuwe klant", "luo asiakas", "uusi asiakas",
        ],
        "anti_keywords": ["slett", "delete", "fjern", "remove", "oppdater", "update", "endre", "change"],
    },
    TaskType.FIND_CUSTOMER: {
        "keywords": [
            "finn kunde", "søk kunde", "søk etter kunde", "find customer",
            "search customer", "look up customer", "buscar cliente",
            "chercher client", "suche kunde", "kunde suchen", "kunde finden",
            # Portuguese / French
            "procurar cliente", "rechercher client", "trouver client",
            # Swedish / Danish
            "hitta kund", "sök kund", "find kunde", "søg kunde",
        ],
    },
    TaskType.CREATE_CREDIT_NOTE: {
        "keywords": [
            "kreditnota", "kreditere faktura", "credit note", "kreditere",
            "gutschrift", "avoir", "créer avoir",
            "nota de crédito", "nota de credito",
        ],
    },
    TaskType.REGISTER_PAYMENT: {
        "keywords": [
            "registrer innbetaling", "registrer betaling", "register payment",
            "record payment", "innbetaling", "registrar pago", "paiement",
            "enregistrer paiement", "zahlung registrieren", "registrar pagamento",
        ],
    },
    TaskType.INVOICE_WITH_PAYMENT: {
        "keywords": [
            "faktura med betaling", "invoice with payment", "already paid",
            "betalt", "innbetalt", "paid in full",
            "facture impayée", "facture impayee", "unbezahlte rechnung",
            "unpaid invoice", "enregistrer le paiement", "zahlung registrieren",
        ],
    },
    TaskType.INVOICE_EXISTING_CUSTOMER: {
        "keywords": [
            "fakturer kunde", "send faktura til", "invoice existing",
            "invoice for existing", "invoice customer", "bill customer",
            "send faktura til kunde", "facturar cliente", "facturer client",
        ],
    },
    TaskType.CREATE_INVOICE: {
        "keywords": [
            "opprett faktura", "opprett en faktura", "opprett ein faktura",
            "lag faktura", "ny faktura",
            "create invoice", "create an invoice", "new invoice",
            "crear factura", "crear una factura",
            "erstellen rechnung", "eine rechnung",
            "créer facture", "créer une facture",
            "criar fatura", "criar uma fatura",
            "fakturer",
            # Swedish / Danish / Dutch / Finnish
            "skapa faktura", "ny faktura", "opret faktura",
            "maak factuur", "nieuwe factuur", "luo lasku", "uusi lasku",
        ],
        "anti_keywords": ["betalt", "paid", "innbetaling", "payment", "kreditnota", "credit note"],
    },
    TaskType.CREATE_PRODUCT: {
        "keywords": [
            "opprett produkt", "opprett et produkt", "opprett eit produkt",
            "nytt produkt",
            "create product", "create a product", "new product",
            "legg til produkt", "register product", "registrer produkt",
            "crear producto", "crear un producto",
            "erstellen produkt", "ein produkt",
            "créer produit", "créer un produit",
            "criar produto", "criar um produto",
            # Swedish / Danish / Dutch / Finnish
            "skapa produkt", "ny produkt", "opret produkt", "nyt produkt",
            "maak product", "nieuw product", "luo tuote", "uusi tuote",
        ],
    },
    TaskType.CREATE_DEPARTMENT: {
        "keywords": [
            "opprett avdeling", "opprett en avdeling", "opprett ei avdeling",
            "opprett ein avdeling",
            "ny avdeling",
            "create department", "create a department", "new department",
            "crear departamento", "crear un departamento",
            "erstellen abteilung", "eine abteilung",
            "créer département", "créer un département",
            "criar departamento", "criar um departamento",
            # Swedish / Danish / Dutch / Finnish
            "skapa avdelning", "ny avdelning", "opret afdeling", "ny afdeling",
            "maak afdeling", "nieuwe afdeling", "luo osasto", "uusi osasto",
        ],
    },
    TaskType.DELETE_PROJECT: {
        "keywords": [
            "slett prosjekt", "fjern prosjekt", "delete project", "remove project",
            "eliminar proyecto", "supprimer projet", "löschen projekt",
        ],
    },
    TaskType.UPDATE_PROJECT: {
        "keywords": [
            "oppdater prosjekt", "endre prosjekt", "update project", "modify project",
            "actualizar proyecto", "modifier projet",
        ],
    },
    TaskType.PROJECT_WITH_CUSTOMER: {
        "keywords": [
            "prosjekt for kunde", "prosjekt til kunde", "project for customer",
            "project linked to customer", "proyecto para cliente",
            "projet pour client",
        ],
    },
    TaskType.CREATE_PROJECT: {
        "keywords": [
            "opprett prosjekt", "opprett eit prosjekt", "opprett ein prosjekt",
            "nytt prosjekt", "create project", "new project",
            "crear proyecto", "erstellen projekt", "créer projet", "criar projeto",
            # Swedish / Danish / Dutch / Finnish
            "skapa projekt", "nytt projekt", "opret projekt", "nyt projekt",
            "maak project", "nieuw project", "luo projekti", "uusi projekti",
        ],
        "anti_keywords": ["slett", "delete", "fjern", "remove", "oppdater", "update", "endre", "change", "aktiver", "modul", "enable module"],
    },
    TaskType.DELETE_TRAVEL_EXPENSE: {
        "keywords": [
            "slett reiseregning", "fjern reiseregning", "delete travel expense",
            "remove travel expense", "slett reiserekning", "fjern reiserekning",
        ],
    },
    TaskType.CREATE_TRAVEL_EXPENSE: {
        "keywords": [
            "reiseregning", "reiserekning", "travel expense", "travel report",
            "reisekostnad", "gastos de viaje", "reisekosten",
            "frais de voyage", "note de frais", "despesas de viagem",
            "opprett reise", "create travel",
            # Swedish / Danish / Dutch / Finnish
            "reseräkning", "resa", "rejseafregning", "rejse",
            "reisdeclaratie", "reis", "matkakulut", "matka", "matkalasku",
        ],
        "anti_keywords": ["slett", "delete", "fjern", "remove"],
    },
    TaskType.CREATE_CONTACT: {
        "keywords": [
            "opprett kontakt", "opprett ein kontakt", "ny kontakt",
            "create contact", "new contact",
            "kontaktperson", "contact person", "add contact", "legg til kontakt",
            "crear contacto", "créer contact", "créer un contact", "kontakt erstellen",
            "contact pour", "contato para", "contacto para",
            # Swedish / Danish / Dutch / Finnish
            "skapa kontakt", "ny kontakt", "opret kontakt",
            "maak contact", "nieuw contact", "luo yhteyshenkilö",
        ],
    },
    TaskType.PROJECT_BILLING: {
        "keywords": [
            "fakturer prosjekt", "invoice project", "project billing",
            "bill project", "faktura for prosjekt", "prosjektfaktura",
        ],
    },
    TaskType.BANK_RECONCILIATION: {
        "keywords": [
            "bankavsteming", "bankavstemming", "bank reconciliation",
            "reconcile bank", "avstem bank", "reconciliación bancaria",
            # German / French / Portuguese
            "bankabstimmung", "kontoabstimmung", "rapprochement bancaire",
            "reconciliação bancária", "conciliação bancária",
            # Swedish / Danish
            "bankavstämning", "bankafstemning",
        ],
    },
    TaskType.ERROR_CORRECTION: {
        "keywords": [
            "korriger", "rett feil", "correct error", "error correction",
            "reverser bilag", "reverse voucher", "feilretting",
            # German / French / Spanish / Portuguese
            "fehlerkorrektur", "buchungskorrektur", "correction d'erreur",
            "corriger écriture", "corrección de error", "correção de erro",
            # Additional Norwegian
            "korrigere bilag", "endre bilag", "rett opp feil",
        ],
    },
    TaskType.YEAR_END_CLOSING: {
        "keywords": [
            "årsavslutning", "årsoppgjør", "year-end", "year end closing",
            "annual closing", "cierre anual",
            # German / French / Portuguese
            "jahresabschluss", "clôture annuelle", "encerramento anual",
            # Swedish / Danish
            "årsbokslut", "årsafslutning",
            # ASCII variants (no special chars)
            "arsavslutning", "aarsavslutning", "year.end", "arsslutt",
            "aarsoppgjor", "arsoppgjor",
        ],
    },
    TaskType.ENABLE_MODULE: {
        "keywords": [
            "aktiver modul", "enable module", "slå på modul", "activate module",
            "activar módulo", "activer module",
            # German / Portuguese
            "modul aktivieren", "ativar módulo",
            # Swedish / Danish
            "aktivera modul", "aktiver modul",
            # ASCII variants
            "slaa paa modul", "aktiver modulen",
        ],
        "anti_keywords": ["opprett prosjekt", "create project", "nytt prosjekt", "new project"],
    },
    TaskType.UPDATE_CONTACT: {
        "keywords": [
            "oppdater kontakt", "endre kontakt", "update contact", "modify contact",
            "change contact", "edit contact", "rediger kontakt",
            "modifier contact", "actualizar contacto", "ändern kontakt",
            "atualizar contato", "oppdater kontaktperson", "endre kontaktperson",
        ],
    },
    TaskType.DELETE_CUSTOMER: {
        "keywords": [
            "slett kunde", "fjern kunde", "delete customer", "remove customer",
            "supprimer client", "eliminar cliente", "löschen kunde",
            "excluir cliente", "remover cliente",
        ],
    },
    TaskType.UPDATE_DEPARTMENT: {
        "keywords": [
            "oppdater avdeling", "endre avdeling", "update department", "modify department",
            "change department", "edit department", "rediger avdeling",
            "modifier département", "actualizar departamento", "ändern abteilung",
            "atualizar departamento",
        ],
    },
    TaskType.CREATE_DIMENSION_VOUCHER: {
        "keywords": [
            "dimensjon", "dimension", "buchhaltungsdimension", "fri dimensjon",
            "custom dimension", "benutzerdefinierte dimension",
            "kostsenter", "kostenstelle", "cost center", "centre de coût",
            "centro de costo", "centro de custo",
            "dimensjonsverdier", "dimensionswert",
            # Norwegian accounting: "bokfør bilag" / "bokför bilag" (Swe spelling)
            "bokfør bilag", "bokför bilag", "bokfør et bilag",
            "bokför ett bilag",
            # Swedish
            "bokföringsdimension", "anpassad dimension",
            # Danish
            "bogføringsdimension", "brugerdefineret dimension",
        ],
    },
    TaskType.RUN_PAYROLL: {
        "keywords": [
            "kjør lønn", "utbetal lønn", "lønnskjøring", "lønnsslipp",
            "run payroll", "execute payroll", "process payroll", "salary payment",
            "paie", "exécutez la paie", "exécuter la paie", "fiche de paie", "bulletin de paie",
            "gehalt", "gehaltsabrechnung", "lohnabrechnung", "lohn auszahlen",
            "nómina", "ejecutar nómina", "procesar nómina",
            "folha de pagamento", "processar folha",
            "lønn", "lønnsutbetaling",
            "salaire", "salaire de base",
            # Swedish / Danish / Dutch / Finnish
            "kör lön", "löneutbetalning", "lön", "kør løn", "lønudbetaling", "løn",
            "salaris uitbetalen", "salarisverwerking", "salaris",
            "palkka", "palkanmaksu", "suorita palkanmaksu",
            # ASCII variants (no special chars)
            "lonnskjoring", "loennskjoering", "kjor lonn", "loennsslipp",
            "lonn", "lonnsutbetaling",
        ],
    },
    TaskType.CREATE_SUPPLIER: {
        "keywords": [
            "registrer leverandør", "opprett leverandør", "ny leverandør",
            "create supplier", "register supplier", "new supplier",
            "add supplier", "legg til leverandør",
            "registrieren lieferant", "lieferanten registrieren",
            "erstellen lieferant", "neuer lieferant", "einen lieferanten",
            "créer fournisseur", "enregistrer fournisseur", "nouveau fournisseur",
            "crear proveedor", "registrar proveedor", "nuevo proveedor",
            "criar fornecedor", "registrar fornecedor", "novo fornecedor",
            # Swedish / Danish / Dutch / Finnish
            "skapa leverantör", "ny leverantör", "registrera leverantör",
            "opret leverandør", "ny leverandør", "registrer leverandør",
            "maak leverancier", "nieuwe leverancier",
            "luo toimittaja", "uusi toimittaja", "rekisteröi toimittaja",
        ],
        "anti_keywords": ["faktura", "invoice", "rechnung", "facture", "factura"],
    },
    TaskType.CREATE_SUPPLIER_INVOICE: {
        "keywords": [
            "leverandørfaktura", "inngående faktura", "supplier invoice",
            "eingangsrechnung", "facture fournisseur", "factura proveedor",
            "faktura fra leverandør", "mottatt faktura", "motteke faktura",
            "received invoice", "incoming invoice",
            # Portuguese
            "fatura de fornecedor", "fatura do fornecedor",
            # Spanish expanded
            "factura de proveedor", "factura del proveedor",
            # Nynorsk
            "leverandørfaktura", "innkomande faktura",
            # Swedish / Danish
            "leverantörsfaktura", "inkommande faktura",
            "leverandørfaktura", "indgående faktura",
            # ASCII variants + "registrer faktura fra"
            "leverandorfaktura", "registrer faktura fra",
            "faktura fra leverandor", "inngaaende faktura",
        ],
    },
    TaskType.LOG_HOURS: {
        "keywords": [
            "logg timer", "log hours", "registrer timer", "timesheet", "timeliste",
            "timeføring", "registrer tid", "register hours", "record hours",
            "registrar horas", "enregistrer heures", "stunden erfassen",
            "loggfør timer", "føre timer", "før timer",
            # Nynorsk
            "logg timar", "registrer timar", "timeliste",
            # Swedish / Danish / Dutch / Finnish
            "logga timmar", "registrera timmar", "tidrapport",
            "registrer timer", "tidsregistrering",
            "uren registreren", "urenregistratie",
            "kirjaa tunnit", "tuntikirjaus",
            # German
            "stunden buchen", "arbeitszeit erfassen", "zeiterfassung",
            # French
            "saisir heures", "pointage", "saisie de temps",
            # Portuguese / Spanish
            "registrar horas", "registro de horas",
        ],
    },
    TaskType.UPDATE_PRODUCT: {
        "keywords": [
            "oppdater produkt", "endre produkt", "update product", "modify product",
            "change product", "edit product", "rediger produkt",
            "modifier produit", "actualizar producto", "produkt ändern",
            "ändern produkt", "aktualisieren produkt", "atualizar produto",
            # Swedish / Danish / Dutch / Finnish
            "uppdatera produkt", "ändra produkt", "opdater produkt", "ændr produkt",
            "wijzig product", "päivitä tuote", "muokkaa tuote",
        ],
    },
    TaskType.DELETE_PRODUCT: {
        "keywords": [
            "slett produkt", "fjern produkt", "delete product", "remove product",
            "supprimer produit", "eliminar producto", "löschen produkt",
            "excluir produto", "remover produto",
            # Swedish / Danish / Dutch / Finnish
            "ta bort produkt", "radera produkt", "slet produkt", "fjern produkt",
            "verwijder product", "poista tuote",
        ],
    },
    TaskType.UPDATE_SUPPLIER: {
        "keywords": [
            "oppdater leverandør", "endre leverandør", "update supplier", "modify supplier",
            "change supplier", "edit supplier", "rediger leverandør",
            "modifier fournisseur", "actualizar proveedor", "ändern lieferant",
            "aktualisieren lieferant", "atualizar fornecedor",
            # Swedish / Danish / Dutch / Finnish
            "uppdatera leverantör", "ändra leverantör", "opdater leverandør",
            "wijzig leverancier", "päivitä toimittaja",
        ],
    },
    TaskType.DELETE_SUPPLIER: {
        "keywords": [
            "slett leverandør", "fjern leverandør", "delete supplier", "remove supplier",
            "supprimer fournisseur", "eliminar proveedor", "löschen lieferant",
            "excluir fornecedor", "remover fornecedor",
            # Swedish / Danish / Dutch / Finnish
            "ta bort leverantör", "radera leverantör", "slet leverandør",
            "verwijder leverancier", "poista toimittaja",
        ],
    },
    TaskType.FIND_SUPPLIER: {
        "keywords": [
            "finn leverandør", "søk leverandør", "søk etter leverandør",
            "find supplier", "search supplier", "look up supplier",
            "chercher fournisseur", "trouver fournisseur", "rechercher fournisseur",
            "buscar proveedor", "suche lieferant", "lieferant suchen", "lieferant finden",
            "procurar fornecedor",
            # Swedish / Danish / Dutch / Finnish
            "hitta leverantör", "sök leverantör", "find leverandør", "søg leverandør",
            "zoek leverancier", "etsi toimittaja",
        ],
    },
    TaskType.DELETE_DEPARTMENT: {
        "keywords": [
            "slett avdeling", "fjern avdeling", "delete department", "remove department",
            "supprimer département", "eliminar departamento", "löschen abteilung",
            "excluir departamento", "remover departamento",
            # Swedish / Danish / Dutch / Finnish
            "ta bort avdelning", "radera avdelning", "slet afdeling", "fjern afdeling",
            "verwijder afdeling", "poista osasto",
        ],
    },
    TaskType.REVERSE_PAYMENT: {
        "keywords": [
            # Norwegian
            "reverser betaling", "angre betaling", "tilbakefør betaling",
            "tilbakefør", "returnert av banken", "stornere betaling",
            "tilbakeført betaling", "reverser innbetaling",
            "betaling returnert", "betaling ble returnert",
            # Nynorsk
            "reverser betaling", "tilbakefør betaling",
            # English
            "reverse payment", "undo payment", "cancel payment",
            "payment returned", "payment bounced", "returned by bank",
            "bounced by bank", "payment was returned", "reverse the payment",
            # Swedish
            "återför betalning", "ångra betalning", "betalning returnerad",
            "återbetala", "storner betalning",
            # Danish
            "tilbagefør betaling", "betaling returneret",
            # German
            "zahlung rückerstattet", "zahlung stornieren", "rückbuchung",
            "zahlung zurückgebucht", "zahlung rückgängig", "stornierung",
            # French
            "paiement retourné", "annuler paiement", "paiement rejeté",
            "retourné par la banque", "reverser le paiement",
            # Spanish
            "pago devuelto", "revertir pago", "pago rechazado",
            "devuelto por el banco", "anular pago",
            # Portuguese
            "pagamento devolvido", "reverter pagamento", "pagamento rejeitado",
            "devolvido pelo banco", "estornar pagamento",
            # Dutch / Finnish
            "betaling terugboeken", "peruuta maksu",
            "betaling geweigerd", "maksu palautettu",
        ],
    },
}

# Pre-compiled regex patterns for field extraction
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RE_PHONE = re.compile(r"(?:\+\d{1,3}\s?)?(?:\d[\d\s\-]{6,14}\d)")
_RE_ORG_NR = re.compile(r"(?:org(?:anisas?tion(?:s?nummer)?)?\.?\s*(?:n[rº]\.?|nummer|number|numéro|número)?\s*:?\s*)(\d[\d\s]{7,10}\d)", re.IGNORECASE)
_RE_DATE_DMY = re.compile(r"\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\b")
_RE_DATE_YMD = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_RE_DATE_TEXT_NB = re.compile(
    r"\b(\d{1,2})\.?\s*(januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember)\s*(\d{4})\b",
    re.IGNORECASE,
)
_MONTH_NB = {
    "januar": 1, "februar": 2, "mars": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}
_RE_AMOUNT = re.compile(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(?:kr|nok|eur|usd|NOK|EUR|USD)", re.IGNORECASE)
_RE_AMOUNT_PRICE = re.compile(r"(?:pris|price|prix|precio|preis|preço)\s+(\d[\d\s]*(?:[.,]\d+)?)", re.IGNORECASE)
_RE_AMOUNT_UNIT = re.compile(r"(?:à|@|a)\s*(\d[\d\s]*(?:[.,]\d+)?)\s*(?:kr|nok)?", re.IGNORECASE)
_RE_QUANTITY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:stk|enheter|timer|units?|hours?|pcs|unidades?|heures?|Stunden?|horas?)", re.IGNORECASE)

# Preposition+name phrases that appear between entity keyword and actual name
_NAME_INTRO_RE = r"(?:med\s+(?:namn\s+|navn(?:et)?\s+)?|with\s+(?:(?:the\s+)?name\s+)?|namens\s+|mit\s+(?:dem\s+)?(?:Namen?\s+)?|appelée?\s+|nommée?\s+|avec\s+(?:le\s+)?(?:nom\s+)?|llamad[oa]\s+|con\s+(?:(?:el\s+)?nombre\s+)?|chamad[oa]\s+|com\s+(?:(?:o\s+)?nome\s+)?|named?\s+|called\s+|kalt\s+|heiter\s+|heter\s+|som\s+heiter\s+|som\s+heter\s+)?"

# Patterns for extracting names after certain keywords
_NAME_PATTERNS = [
    # "med navn X Y, ..." or "med navn X Y og ..." — stop at comma, period, or connector
    re.compile(r"(?:named?|med\s+navn|med\s+namn|(?:som\s+)?heiter|(?:som\s+)?heter|namens|llamad[oa]|appelé[e]?|chamad[oa]|com\s+nome)\s+((?:[A-ZÆØÅ\u00C0-\u024F][\w\-]*\s*){1,4})(?:\s*[,.]|\s+(?:med|with|mit|con|com|avec|og|and|und|et|e|y|fra|from|i|in|phone|telefon|tlf|mobil|mobile)\b)", re.IGNORECASE),
    # Fallback: "named X Y" at end of string
    re.compile(r"(?:named?|med\s+navn|med\s+namn|(?:som\s+)?heiter|(?:som\s+)?heter|namens|llamad[oa]|appelé[e]?|chamad[oa]|com\s+nome)\s+((?:[A-ZÆØÅ\u00C0-\u024F][\w\-]*\s*){1,4})\s*$", re.IGNORECASE),
    # "ansatt [med navn] X Y" — entity keyword + optional name intro + capitalized name
    re.compile(rf"(?:ansatt|tilsett|employee|empleado|mitarbeiter|employé|funcionário)\s+{_NAME_INTRO_RE}((?:[A-ZÆØÅ\u00C0-\u024F][\w\-]*\s*)+?)(?:\s*[,.]|\s+(?:med|with|og|and|und|et|e-post|email|fra|from)\b)", re.IGNORECASE),
    re.compile(rf"(?:ansatt|tilsett|employee|empleado|mitarbeiter|employé|funcionário)\s+{_NAME_INTRO_RE}((?:[A-ZÆØÅ\u00C0-\u024F][\w\-]*\s*)+?)\s*$", re.IGNORECASE),
]

# Customer name patterns — order matters: most specific first
_CUSTOMER_NAME_PATTERNS = [
    # "kunde [med navn] X AS" / "customer [named] X Corp" — company suffix anchored (greedy to capture full name)
    re.compile(rf"(?:kunde|customer|client[e]?|cliente?|Kunde|kunden)\s+{_NAME_INTRO_RE}([A-ZÆØÅ\u00C0-\u024F][\w\s]*(?:AS|ASA|SA|GmbH|Ltd|Inc|Corp|AB|ApS|AG|SRL|SARL|Lda|SL))\b", re.IGNORECASE),
    # "for customer [named] X AS" / "for kunde [med navn] X AS"
    re.compile(rf"(?:for|til|para|pour|für|per)\s+(?:el\s+)?(?:kunde\s+|customer\s+|client[e]?\s+|cliente?\s+|Kunden?\s+)?{_NAME_INTRO_RE}([A-ZÆØÅ\u00C0-\u024F][\w\s]*(?:AS|ASA|SA|GmbH|Ltd|Inc|Corp|AB|ApS|AG))\b", re.IGNORECASE),
    # "kunde [med navn] X Y" followed by delimiter
    re.compile(rf"(?:kunde|customer|client[e]?|cliente?|Kunde|kunden)\s+{_NAME_INTRO_RE}([A-ZÆØÅ\u00C0-\u024F][\w\s]+?)(?:\s*[,.]|\s+(?:med|with|for|por|pour|mit|og|and|und|et|e|y|fra|from|telefon|phone|tlf|mobil|mobile)\s)", re.IGNORECASE),
    # "kunde [med navn] X Y" at end of string
    re.compile(rf"(?:kunde|customer|client[e]?|cliente?|Kunde|kunden)\s+{_NAME_INTRO_RE}([A-ZÆØÅ\u00C0-\u024F][\w\s]+?)\s*$", re.IGNORECASE),
    # "for/til X Y" with company-like name (capitalized, multi-word)
    re.compile(rf"(?:for|til|para|pour|für|per)\s+(?:el\s+)?(?:kunde\s+|customer\s+|client[e]?\s+|cliente?\s+|Kunden?\s+)?{_NAME_INTRO_RE}([A-ZÆØÅ\u00C0-\u024F][\w]+(?:\s+[A-ZÆØÅ\u00C0-\u024F][\w]+)+)(?:\s*[,.]|\s+(?:med|with|og|and|por|pour|mit|fra|from|telefon|phone|tlf|mobil|mobile)\s|$)", re.IGNORECASE),
    # "named/namens/llamado X" patterns for customers (standalone, no entity keyword)
    re.compile(r"(?:namens|llamad[oa]|named?|kalt)\s+([A-ZÆØÅ\u00C0-\u024F][\w\s]*(?:AS|ASA|SA|GmbH|Ltd|Inc|Corp|AB|ApS|AG))\b", re.IGNORECASE),
    re.compile(r"(?:namens|llamad[oa]|named?|kalt)\s+([A-ZÆØÅ\u00C0-\u024F][\w]+(?:\s+[A-ZÆØÅ\u00C0-\u024F][\w]+)+)", re.IGNORECASE),
]

# Department/product/project name: "called X" / "kalt X" / "appelé X"
_THING_NAME_PATTERNS = [
    # "called X" / "appelé X" / "kalt X" / "llamado X" / "chamado X"
    re.compile(r"(?:kalt|called|heiter|heter|appelé[e]?|nommé[e]?|llamad[oa]|chamad[oa]|genannt|het|hetende)\s+['\"]?(.+?)['\"]?(?:\s*[,.]|\s+(?:med|with|for|og|and|et|mit|pour|para|con|com|fra|from|til|at|zu|à|nummer|number)\s|$)", re.IGNORECASE),
    # "avdeling [kalt] X" / "department [named] X" etc. — entity keyword + optional name intro + name
    re.compile(rf"(?:avdeling|department|département|departamento|Abteilung)\s+{_NAME_INTRO_RE}['\"]?([A-ZÆØÅ\u00C0-\u024F][\w\s-]+?)['\"]?(?:\s*[,.]|\s+(?:med|with|for|og|and|et|mit|pour|para|con|com|fra|from|til|at|zu|à|nummer|number)\s|$)", re.IGNORECASE),
    re.compile(rf"(?:prosjekt|project|projet|proyecto|projeto)\s+{_NAME_INTRO_RE}['\"]?([A-ZÆØÅ\u00C0-\u024F][\w\s-]+?)['\"]?(?:\s*[,.]|\s+(?:med|with|for|og|and|et|mit|pour|para|con|com|fra|from|til|at|zu|à)\s|$)", re.IGNORECASE),
    re.compile(rf"(?:produkt|product|produit|producto|produto)\s+{_NAME_INTRO_RE}['\"]?([A-ZÆØÅ\u00C0-\u024F][\w\s-]+?)['\"]?(?:\s*[,.]|\s+(?:med|with|for|og|and|et|mit|pour|para|con|com|fra|from|pris|price|prix|til|at|zu|à)\s|$)", re.IGNORECASE),
]


_NAME_PREFIXES = [
    "med navnet", "med namn", "med navn", "med fornavn", "med etternavn",
    "with name", "with the name",
    "mit dem namen", "namens", "genannt",
    "avec le nom", "nommée", "nommé", "appelée", "appelé",
    "con nombre", "con el nombre", "llamada", "llamado", "denominado",
    "com nome", "com o nome", "chamada", "chamado",
    "named", "called", "kalt", "heter", "heiter",
    "som heter", "som heiter",
]

_NAME_SUFFIX_CONNECTORS = [
    " og ", " and ", " und ", " et ", " y ", " e ",
    " med ", " with ", " mit ", " avec ", " con ", " com ",
]

_FIELD_INDICATOR_WORDS = [
    "e-post", "epost", "email", "e-mail", "correo",
    "telefon", "phone", "tlf", "mobil", "mobile", "teléfono",
    "adresse", "address", "dirección", "endereço",
    "avdeling", "department", "abteilung", "département", "departamento",
    "nummer", "number", "número", "numéro",
    "rolle", "role", "tilgang", "access",
    "org", "organisasjon", "organization",
    "start", "dato", "date", "fecha",
]


def _clean_name(raw: str) -> str:
    """Strip multilingual prefix words and trailing connectors from an extracted name."""
    name = raw.strip()
    lower = name.lower()

    # Strip leading prefixes like "med navn", "namens", "called", etc.
    for p in sorted(_NAME_PREFIXES, key=len, reverse=True):
        if lower.startswith(p + " ") or lower.startswith(p + "\t"):
            name = name[len(p):].strip()
            lower = name.lower()
            break

    # Strip trailing connectors ("og", "and", etc.) if followed by a field indicator
    for s in _NAME_SUFFIX_CONNECTORS:
        idx = lower.find(s)
        if idx > 0:
            after = name[idx + len(s):]
            if not after.strip() or any(after.lower().startswith(w) for w in _FIELD_INDICATOR_WORDS):
                name = name[:idx].strip()
                lower = name.lower()
                break

    # Strip trailing contact info phrases like "with email ...", "med e-post ...", "telefon ..."
    _contact_suffix_re = re.compile(
        r'\s+(?:with\s+email|med\s+e-?post|med\s+epost|telefon|phone|tlf|mobil|mobile)\b.*$',
        re.IGNORECASE,
    )
    name = _contact_suffix_re.sub("", name).strip()
    lower = name.lower()

    # Also strip if the name ends with a bare connector word
    for conn in ["og", "and", "und", "et", "y", "e", "med", "with", "mit"]:
        if lower.endswith(" " + conn):
            name = name[:-(len(conn) + 1)].strip()
            break

    return name.rstrip(".,;:")


def _extract_name_parts(prompt: str) -> tuple:
    """Try to extract first_name, last_name from prompt."""
    for pat in _NAME_PATTERNS:
        m = pat.search(prompt)
        if m:
            name = _clean_name(m.group(1).strip().rstrip(",."))
            parts = name.split()
            if len(parts) >= 2:
                return parts[0], " ".join(parts[1:])
            elif len(parts) == 1:
                return parts[0], None
    return None, None


def _extract_dates(prompt: str) -> list:
    """Extract dates from prompt, return list of YYYY-MM-DD strings."""
    dates = []
    # YYYY-MM-DD
    for m in _RE_DATE_YMD.finditer(prompt):
        dates.append(f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
    # DD.MM.YYYY or DD/MM/YYYY
    for m in _RE_DATE_DMY.finditer(prompt):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            dates.append(f"{y}-{mo:02d}-{d:02d}")
        elif 1 <= d <= 12 and 1 <= mo <= 31:
            # Might be MM/DD/YYYY
            dates.append(f"{y}-{d:02d}-{mo:02d}")
    # Textual Norwegian dates
    for m in _RE_DATE_TEXT_NB.finditer(prompt):
        d = int(m.group(1))
        mo = _MONTH_NB.get(m.group(2).lower(), 0)
        y = int(m.group(3))
        if mo and 1 <= d <= 31:
            dates.append(f"{y}-{mo:02d}-{d:02d}")
    return dates


def _parse_amount(s: str) -> float:
    """Parse a numeric string with possible spaces/commas to a float."""
    s = s.replace(" ", "").replace("\u00a0", "")
    # European decimal: "1234,50" → "1234.50"
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(",", "")  # thousand separator
    return float(s)


def _extract_amounts(prompt: str) -> list:
    """Extract monetary amounts from prompt."""
    amounts = []
    for m in _RE_AMOUNT.finditer(prompt):
        try:
            amounts.append(_parse_amount(m.group(1)))
        except ValueError:
            pass
    # Also match amounts after price keywords without currency suffix (e.g. "pris 1500")
    for m in _RE_AMOUNT_PRICE.finditer(prompt):
        try:
            val = _parse_amount(m.group(1))
            if val not in amounts:
                amounts.append(val)
        except ValueError:
            pass
    return amounts


def _extract_fields_generic(prompt: str, task_type: TaskType) -> dict:
    """Extract fields from prompt using regex patterns. Best-effort."""
    fields: dict[str, Any] = {}

    # Email
    email_match = _RE_EMAIL.search(prompt)
    if email_match:
        fields["email"] = email_match.group(0).rstrip(".")

    # Phone — skip if the match is preceded by org number keywords
    phone_match = _RE_PHONE.search(prompt)
    if phone_match:
        phone_val = phone_match.group(0).strip()
        # Don't treat org numbers as phone numbers
        before_phone = prompt[:phone_match.start()].lower()
        if not re.search(r"(?:org(?:anisas?tion(?:s?nummer)?)?\.?\s*(?:n[rº]\.?|nummer|number|numéro|número)?\s*:?\s*)$", before_phone):
            fields["phone"] = phone_val

    # Org number
    org_match = _RE_ORG_NR.search(prompt)
    if org_match:
        fields["organization_number"] = org_match.group(1).replace(" ", "")

    # Dates
    dates = _extract_dates(prompt)

    # Amounts
    amounts = _extract_amounts(prompt)

    # Unit price from "à X kr" patterns
    unit_match = _RE_AMOUNT_UNIT.search(prompt)
    unit_price = None
    if unit_match:
        try:
            unit_price = _parse_amount(unit_match.group(1))
        except ValueError:
            pass

    # Quantity
    qty_match = _RE_QUANTITY.search(prompt)
    quantity = None
    if qty_match:
        try:
            quantity = _parse_amount(qty_match.group(1))
        except ValueError:
            pass

    # VAT percentage
    vat_match = re.search(r"(\d+)\s*%\s*(?:MVA|mva|MwSt|Steuersatz|VAT|TVA|IVA|taux|tax)", prompt, re.IGNORECASE)
    if not vat_match:
        vat_match = re.search(r"(?:MVA|mva|MwSt|Steuersatz|VAT|TVA|IVA|taux|tax)\s*:?\s*(\d+)\s*%?", prompt, re.IGNORECASE)
    if vat_match:
        fields["vat_percentage"] = int(vat_match.group(1))

    # --- Task-specific field extraction ---

    if task_type in (TaskType.CREATE_EMPLOYEE, TaskType.DELETE_EMPLOYEE,
                     TaskType.UPDATE_EMPLOYEE, TaskType.SET_EMPLOYEE_ROLES):
        # Handle "fornavn X og etternavn Y" / "fornavn X etternavn Y" pattern first
        fn_match = re.search(r"fornavn\s+(\S+)\s+(?:og\s+)?etternavn\s+(\S+)", prompt, re.IGNORECASE)
        if fn_match:
            fields["first_name"] = fn_match.group(1).rstrip(",.")
            fields["last_name"] = fn_match.group(2).rstrip(",.")
        else:
            first_name, last_name = _extract_name_parts(prompt)
            if first_name:
                fields["first_name"] = first_name
            if last_name:
                fields["last_name"] = last_name
        if not fields.get("first_name") and not fields.get("last_name"):
            # Try to find employee_identifier
            fields["employee_identifier"] = _guess_entity_name(prompt, [
                "ansatt", "tilsett", "employee", "empleado", "mitarbeiter", "employé", "funcionário",
            ])
        # NOTE: Do NOT set start_date for employees — Tripletex Employee API
        # does not have a startDate field and rejects it with 422.

    elif task_type in (TaskType.CREATE_CUSTOMER, TaskType.UPDATE_CUSTOMER):
        name = _guess_customer_name(prompt)
        if name:
            fields["name"] = name
        if dates:
            fields["start_date"] = dates[0]

    elif task_type == TaskType.FIND_CUSTOMER:
        if org_match:
            fields["search_query"] = fields.get("organization_number", "")
            fields["search_field"] = "organization_number"
        elif email_match:
            fields["search_query"] = fields.get("email", "")
            fields["search_field"] = "email"
        else:
            name = _guess_customer_name(prompt)
            if name:
                fields["search_query"] = name
                fields["search_field"] = "name"

    elif task_type in (TaskType.CREATE_INVOICE, TaskType.INVOICE_EXISTING_CUSTOMER,
                       TaskType.INVOICE_WITH_PAYMENT):
        cust = _guess_customer_name(prompt)
        if cust:
            fields["customer_name"] = cust
        # Try structured line extraction first: "N stk X til Y kr"
        extracted_lines = _extract_invoice_lines(prompt)
        if extracted_lines:
            fields["lines"] = extracted_lines
        else:
            # Fallback: simple single-line extraction
            line: dict[str, Any] = {}
            if unit_price is not None:
                line["unit_price"] = unit_price
            elif amounts:
                line["unit_price"] = amounts[0]
            if quantity is not None:
                line["quantity"] = quantity
            if line:
                fields["lines"] = [line]
        if dates:
            fields["invoice_date"] = dates[0]
            if len(dates) > 1:
                fields["due_date"] = dates[1]
        if task_type == TaskType.INVOICE_WITH_PAYMENT and amounts:
            # Total = qty * unit_price or largest amount
            if quantity and unit_price:
                fields["paid_amount"] = quantity * unit_price
            else:
                fields["paid_amount"] = max(amounts)

    elif task_type == TaskType.CREATE_PRODUCT:
        name = _guess_thing_name(prompt)
        if name:
            fields["name"] = name
        if amounts:
            fields["price_excluding_vat"] = amounts[0]
        # Product number: "produktnummer 5524" / "product number 5524" / "med nummer 5524"
        prod_nr_match = re.search(
            r"(?:produktnummer|product\s*number|Produktnummer|numéro\s*de\s*produit|número\s*de\s*producto|"
            r"(?:med|with|mit|og|and|avec|con)\s+(?:nummer|number|Nummer|numéro|número))\s*:?\s*(\d+)",
            prompt, re.IGNORECASE,
        )
        if prod_nr_match:
            fields["number"] = prod_nr_match.group(1)
        elif "number" not in fields:
            # Fallback: standalone "nummer/number/nr N" (only for product tasks)
            nr_match = re.search(r"(?:nummer|number|nr\.?)\s*:?\s*(\d+)", prompt, re.IGNORECASE)
            if nr_match:
                fields["number"] = nr_match.group(1)

    elif task_type in (TaskType.CREATE_DEPARTMENT,):
        name = _guess_thing_name(prompt)
        if name:
            fields["name"] = name
        # Extract department number: "avdelingsnummer 40", "med nummer 40", "numéro 90", "number 50"
        dept_nr_match = re.search(
            r"(?:avdelingsnummer|department\s*number|abteilungsnummer|"
            r"numéro\s*(?:de\s*)?département|número\s*(?:de\s*)?departamento|"
            r"(?:med|with|mit|og|and|avec|con)\s+(?:nummer|number|Nummer|numéro|número)|"
            r"(?:numéro|número|nummer|number|nr\.?))"
            r"\s*:?\s*(\d+)",
            prompt, re.IGNORECASE,
        )
        if dept_nr_match:
            fields["department_number"] = dept_nr_match.group(1)

    elif task_type in (TaskType.CREATE_PROJECT, TaskType.PROJECT_WITH_CUSTOMER,
                       TaskType.UPDATE_PROJECT, TaskType.DELETE_PROJECT):
        name = _guess_thing_name(prompt)
        if name:
            fields["name"] = name
            fields["project_name"] = name
        cust = _guess_customer_name(prompt)
        if cust:
            fields["customer_name"] = cust
            fields["customer_identifier"] = cust
        if dates:
            fields["start_date"] = dates[0]
            if len(dates) > 1:
                fields["end_date"] = dates[1]
        if amounts:
            fields["fixed_price"] = amounts[0]
            fields["is_fixed_price"] = True

    elif task_type == TaskType.CREATE_TRAVEL_EXPENSE:
        first_name, last_name = _extract_name_parts(prompt)
        if first_name and last_name:
            fields["employee_identifier"] = f"{first_name} {last_name}"
        if dates:
            fields["departure_date"] = dates[0]
            fields["return_date"] = dates[-1]

        # Departure / destination: "fra X til Y" / "from X to Y"
        route_match = re.search(r"(?:fra|from|von|de|desde)\s+([A-ZÆØÅ\u00C0-\u024F][\w\s-]+?)\s+(?:til|to|nach|à|a|hasta)\s+([A-ZÆØÅ\u00C0-\u024F][\w\s-]+?)(?:\s*[,.]|\s+\d|\s+(?:den|the|le|el|am|on|i|in)\s|$)", prompt, re.IGNORECASE)
        if route_match:
            fields["departure_from"] = route_match.group(1).strip().rstrip(",.")
            fields["destination"] = route_match.group(2).strip().rstrip(",.")

        # Purpose: "formål: X" / "purpose: X" / "Zweck: X" / "objet: X"
        purpose_match = re.search(r"(?:formål|purpose|zweck|objet|objeto|finalidade)\s*:?\s+(.+?)(?:\s*[,.]|$)", prompt, re.IGNORECASE)
        if purpose_match:
            fields["purpose"] = purpose_match.group(1).strip().rstrip(",.")

        # Title: "tittel X" / "title X", or fallback to first meaningful phrase
        title_match = re.search(r"(?:tittel|title)\s*:?\s+(.+?)(?:\s*[,.]|\s+(?:for|hos)\s|$)", prompt, re.IGNORECASE)
        if title_match:
            fields["title"] = title_match.group(1).strip().rstrip(",.")
        elif "title" not in fields:
            # Fallback: extract text between "reiseregning/travel expense" and "for ansatt/employee"
            t_match = re.search(
                r"(?:reiseregning|reiserekning|travel\s*expense|reisekostenabrechnung|note\s*de\s*frais)\s+(.+?)\s+(?:for\s+(?:ansatt|tilsett|employee|mitarbeiter|employé|empleado)|$)",
                prompt, re.IGNORECASE,
            )
            if t_match:
                candidate = t_match.group(1).strip().rstrip(",.")
                if candidate and not re.match(r"^(?:for|til|to)\s", candidate, re.IGNORECASE):
                    fields["title"] = candidate

    elif task_type in (TaskType.REGISTER_PAYMENT, TaskType.CREATE_CREDIT_NOTE):
        # Look for invoice number
        inv_match = re.search(r"(?:faktura|invoice|rechnung|factura?)\s*(?:nr\.?\s*)?#?\s*(\d+)", prompt, re.IGNORECASE)
        if inv_match:
            fields["invoice_identifier"] = inv_match.group(1)
            fields["invoice_number"] = inv_match.group(1)
        if amounts and task_type == TaskType.REGISTER_PAYMENT:
            fields["amount"] = amounts[0]
        if dates:
            fields["payment_date"] = dates[0]

    elif task_type == TaskType.CREATE_CONTACT:
        first_name, last_name = _extract_name_parts(prompt)
        if first_name:
            fields["first_name"] = first_name
        if last_name:
            fields["last_name"] = last_name
        cust = _guess_customer_name(prompt)
        if cust:
            fields["customer_identifier"] = cust

    elif task_type == TaskType.RUN_PAYROLL:
        # Extract employee name
        first_name, last_name = _extract_name_parts(prompt)
        if first_name:
            fields["first_name"] = first_name
        if last_name:
            fields["last_name"] = last_name
        if first_name and last_name:
            fields["employee_identifier"] = f"{first_name} {last_name}"
        # Base salary: "salaire de base est de 56950" / "grunnlønn 45000" / "base salary 45000"
        base_match = re.search(
            r"(?:salaire\s+de\s+base|grunnlønn|grundgehalt|base\s+salary|sueldo\s+base|salário\s+base|basislønn)\s+(?:est\s+de\s+|er\s+|ist\s+|es\s+|é\s+)?(\d[\d\s.,]*)\s*(?:kr|NOK)?",
            prompt, re.IGNORECASE,
        )
        if base_match:
            fields["base_salary"] = float(base_match.group(1).replace(",", ".").replace(" ", ""))
        elif amounts:
            fields["base_salary"] = amounts[0]
        # Bonus: "prime unique de 9350" / "bonus 9350" / "tillegg 9350"
        bonus_match = re.search(
            r"(?:prime|bonus|tillegg|Bonus|Zuschlag|Prämie|bonificación|bônus|gratification)\s+(?:unique\s+)?(?:de\s+|på\s+|von\s+|of\s+)?(\d[\d\s.,]*)\s*(?:kr|NOK)?",
            prompt, re.IGNORECASE,
        )
        if bonus_match:
            fields["bonus"] = float(bonus_match.group(1).replace(",", ".").replace(" ", ""))

    elif task_type == TaskType.CREATE_SUPPLIER:
        # Extract supplier name: "Lieferanten X GmbH" / "leverandør X AS" / "supplier X"
        sup_match = re.search(
            r"(?:leverandør(?:en)?|supplier|fournisseur|lieferant(?:en)?|proveedor|fornecedor)\s+"
            r"([A-ZÆØÅ\u00C0-\u024F][\w\s]*?(?:AS|ASA|SA|GmbH|Ltd|Inc|Corp|AB|ApS|AG|SRL|SARL|Lda|SL)?)\b"
            r"(?:\s*[,(.]|\s+(?:med|with|org|på|for|til|mit|avec|con)\s|$)",
            prompt, re.IGNORECASE,
        )
        if sup_match:
            fields["name"] = sup_match.group(1).strip().rstrip(",.")

    elif task_type == TaskType.CREATE_SUPPLIER_INVOICE:
        # Extract supplier name: "leverandøren X" / "fra leverandør X" / "supplier X"
        sup_match = re.search(
            r"(?:leverandør(?:en)?|supplier|fournisseur|lieferant|proveedor)\s+"
            r"([A-ZÆØÅ\u00C0-\u024F][\w\s]*?(?:AS|ASA|SA|GmbH|Ltd|Inc|Corp|AB|ApS|AG|SRL|SARL|Lda|SL)?)\b"
            r"(?:\s*[,(.]|\s+(?:med|with|org|på|for|til)\s|$)",
            prompt, re.IGNORECASE,
        )
        if sup_match:
            fields["supplier_name"] = sup_match.group(1).strip().rstrip(",.")
        if amounts:
            fields["amount_including_vat"] = amounts[0]
        if dates:
            fields["invoice_date"] = dates[0]

    elif task_type == TaskType.REVERSE_PAYMENT:
        # Extract customer name
        cust = _guess_customer_name(prompt)
        if cust:
            fields["customer_name"] = cust
        # Invoice number if mentioned
        inv_match = re.search(r"(?:faktura|invoice|rechnung|factura?)\s*(?:nr\.?\s*)?#?\s*(\d+)", prompt, re.IGNORECASE)
        if inv_match:
            fields["invoice_number"] = inv_match.group(1)
        if amounts:
            fields["amount"] = amounts[0]

    elif task_type == TaskType.CREATE_DIMENSION_VOUCHER:
        # Extract quoted values for dimension_name and dimension_values
        quoted = re.findall(r"['\u2018\u2019\u201C\u201D\"']([^'\u2018\u2019\u201C\u201D\"']+)['\u2018\u2019\u201C\u201D\"']", prompt)
        if quoted:
            fields["dimension_name"] = quoted[0]
            if len(quoted) > 1:
                # linked_dimension_value: look for association keyword + quoted value
                link_match = re.search(
                    r"(?:verknüpft|linked|knyttet|lié|vinculado|associé)\s+(?:mit|with|til|med|à|a|con)?\s*(?:dem\s+)?(?:Dimensionswert|dimension\s*value?|dimensjonsverdien?)?\s*['\u2018\u2019\u201C\u201D\"']([^'\u2018\u2019\u201C\u201D\"']+)['\u2018\u2019\u201C\u201D\"']",
                    prompt, re.IGNORECASE,
                )
                if link_match:
                    fields["linked_dimension_value"] = link_match.group(1)
                # Deduplicate values and exclude the dimension name itself
                seen = set()
                dim_values = []
                for q in quoted[1:]:
                    if q.lower() != quoted[0].lower() and q.lower() not in seen:
                        seen.add(q.lower())
                        dim_values.append(q)
                fields["dimension_values"] = dim_values
        # Account number: "Konto 7000" / "account 7000" / "konto 6000"
        acct_match = re.search(r"(?:Konto|konto|account|compte|cuenta|conta|Buchungskonto)\s+(\d{4})", prompt, re.IGNORECASE)
        if acct_match:
            fields["account_number"] = acct_match.group(1)
        # Amount
        if amounts:
            fields["amount"] = amounts[0]
        if dates:
            fields["voucher_date"] = dates[0]

    return fields


def _guess_entity_name(prompt: str, entity_keywords: list) -> str:
    """Try to find the name of an entity after entity keywords."""
    for kw in entity_keywords:
        pat = re.compile(
            rf"\b{re.escape(kw)}\s+([A-ZÆØÅ][\w]*(?:\s+[A-ZÆØÅ][\w]*)*)",
            re.IGNORECASE,
        )
        m = pat.search(prompt)
        if m:
            return _clean_name(m.group(1).strip().rstrip(",."))
    return ""


def _guess_customer_name(prompt: str) -> str:
    """Try to extract a customer/company name from the prompt."""
    for pat in _CUSTOMER_NAME_PATTERNS:
        m = pat.search(prompt)
        if m:
            return _clean_name(m.group(1).strip().rstrip(",."))
    return ""


def _guess_thing_name(prompt: str) -> str:
    """Try to extract a generic thing name (department, project, product)."""
    for pat in _THING_NAME_PATTERNS:
        m = pat.search(prompt)
        if m:
            return _clean_name(m.group(1).strip().rstrip(",."))
    # Try quoted names
    quoted = re.search(r"['\"](.+?)['\"]", prompt)
    if quoted:
        return quoted.group(1).strip()
    return ""


def _extract_invoice_lines(text: str) -> list[dict]:
    """Extract invoice lines from natural language text.

    Patterns: "N stk/pcs X til/at/à Y kr" and "X - N stk à Y kr".
    """
    lines = []

    # Pattern: "N stk/pcs X til/at/for/à Y kr"
    for m in re.finditer(
        r"(\d+)\s*(?:stk|pcs|units?|x)\s+(.+?)\s+(?:til|at|for|à|@)\s*(\d+[\d.,]*)\s*(?:kr|NOK|,-)?",
        text, re.IGNORECASE
    ):
        qty = int(m.group(1))
        desc = m.group(2).strip().rstrip(",.")
        price = float(m.group(3).replace(",", ".").replace(" ", ""))
        lines.append({"description": desc, "quantity": qty, "unit_price": price})

    # Pattern: "X - N stk à Y kr"
    if not lines:
        for m in re.finditer(
            r"(.+?)[\s:,-]+(\d+)\s*(?:stk|pcs|units?)\s*(?:à|@|til|at|for)\s*(\d+[\d.,]*)\s*(?:kr|NOK)?",
            text, re.IGNORECASE
        ):
            desc = m.group(1).strip().rstrip(",.-:")
            qty = int(m.group(2))
            price = float(m.group(3).replace(",", ".").replace(" ", ""))
            if desc and len(desc) < 100:
                lines.append({"description": desc, "quantity": qty, "unit_price": price})

    # Pattern: "N stk/pcs X" without explicit price (price=0, product lookup needed)
    if not lines:
        for m in re.finditer(
            r"(\d+)\s*(?:stk|pcs|units?|x)\s+([A-ZÆØÅa-zæøå\u00C0-\u024F][\w\s&-]{1,50}?)(?:\s*[,.]|\s+\d+\s*(?:stk|pcs|units?|x)\s|\s*$)",
            text, re.IGNORECASE
        ):
            qty = int(m.group(1))
            desc = m.group(2).strip().rstrip(",.")
            if desc and len(desc) < 80:
                lines.append({"description": desc, "quantity": qty, "unit_price": 0.0})

    return lines


def _last_resort_classify(prompt: str) -> TaskClassification:
    """Ultra-simple single-word heuristic. NEVER return UNKNOWN if any signal exists."""
    p = prompt.lower()
    # Order matters — more specific matches first
    _LAST_RESORT = [
        # Supplier invoice before regular invoice
        # Dimension/voucher before invoice/voucher
        (["dimensjon", "dimension", "buchhaltungsdimension", "kostsenter", "kostenstelle", "cost center", "fri dimensjon", "custom dimension"], TaskType.CREATE_DIMENSION_VOUCHER),
        (["lønn", "lonn", "payroll", "paie", "gehalt", "nómina", "salaire", "lønnskjøring", "lonnskjoring", "lønnsslipp", "lonnsslipp", "salary"], TaskType.RUN_PAYROLL),
        (["leverandørfaktura", "leverandorfaktura", "inngående faktura", "inngaaende faktura", "eingangsrechnung", "supplier invoice", "facture fournisseur"], TaskType.CREATE_SUPPLIER_INVOICE),
        (["leverandør", "supplier", "fournisseur", "lieferant", "lieferanten", "proveedor", "fornecedor"], TaskType.CREATE_SUPPLIER),
        # Reverse payment before credit note (both deal with "undo" but reverse_payment is for bank returns)
        (["reverser", "reverse payment", "tilbakefør", "stornere", "rückbuchung", "bounced", "returned by bank", "returnert av banken", "devolvido pelo banco", "pago devuelto", "paiement retourné"], TaskType.REVERSE_PAYMENT),
        # Credit note before invoice
        (["kreditnota", "credit note", "gutschrift", "avoir", "nota de crédito"], TaskType.CREATE_CREDIT_NOTE),
        # Invoice+payment before plain invoice
        (["betaling", "payment", "pago", "zahlung", "paiement", "betalt", "paid", "innbetaling"], TaskType.INVOICE_WITH_PAYMENT),
        # Travel before employee
        (["reiseregning", "reiserekning", "travel expense", "reisekostenabrechnung", "note de frais", "gasto de viaje"], TaskType.CREATE_TRAVEL_EXPENSE),
        # Hours/timesheet
        (["timer", "hours", "stunden", "heures", "horas", "timesheet", "timeliste", "timefør", "logg"], TaskType.LOG_HOURS),
        # Bank/year-end/error
        (["bankavstem", "reconcil", "abgleich", "rapprochement"], TaskType.BANK_RECONCILIATION),
        (["årsavslut", "arsavslut", "aarsavslut", "årsoppgjør", "arsoppgjor", "aarsoppgjor", "year-end", "year end", "jahresabschluss", "clôture"], TaskType.YEAR_END_CLOSING),
        (["korriger", "correct", "feil", "error correction"], TaskType.ERROR_CORRECTION),
        (["aktiver modul", "enable module", "slå på", "slaa paa", "activate module"], TaskType.ENABLE_MODULE),
        # Delete patterns (check before create)
        (["slett kunde", "delete customer", "fjern kunde"], TaskType.DELETE_CUSTOMER),
        (["slett ansatt", "delete employee", "fjern ansatt"], TaskType.DELETE_EMPLOYEE),
        (["slett prosjekt", "delete project", "fjern prosjekt"], TaskType.DELETE_PROJECT),
        (["slett reise", "delete travel", "fjern reise"], TaskType.DELETE_TRAVEL_EXPENSE),
        (["slett produkt", "delete product", "fjern produkt"], TaskType.DELETE_PRODUCT),
        (["slett leverandør", "delete supplier", "fjern leverandør"], TaskType.DELETE_SUPPLIER),
        (["slett avdeling", "delete department", "fjern avdeling"], TaskType.DELETE_DEPARTMENT),
        # Update patterns
        (["oppdater ansatt", "update employee", "endre ansatt"], TaskType.UPDATE_EMPLOYEE),
        (["oppdater kunde", "update customer", "endre kunde"], TaskType.UPDATE_CUSTOMER),
        (["oppdater prosjekt", "update project", "endre prosjekt"], TaskType.UPDATE_PROJECT),
        (["oppdater kontakt", "update contact", "endre kontakt"], TaskType.UPDATE_CONTACT),
        (["oppdater avdeling", "update department", "endre avdeling"], TaskType.UPDATE_DEPARTMENT),
        (["oppdater produkt", "update product", "endre produkt"], TaskType.UPDATE_PRODUCT),
        (["oppdater leverandør", "update supplier", "endre leverandør"], TaskType.UPDATE_SUPPLIER),
        # Find
        (["finn kunde", "find customer", "søk kunde", "search customer"], TaskType.FIND_CUSTOMER),
        (["finn leverandør", "find supplier", "søk leverandør", "search supplier"], TaskType.FIND_SUPPLIER),
        # Set roles
        (["rolle", "role", "tilgang", "access", "user type"], TaskType.SET_EMPLOYEE_ROLES),
        # Contact
        (["kontaktperson", "contact person", "kontakt"], TaskType.CREATE_CONTACT),
        # Create patterns — broad matches last
        (["faktura", "invoice", "factura", "rechnung", "facture", "fatura"], TaskType.CREATE_INVOICE),
        (["ansatt", "tilsett", "employee", "empleado", "mitarbeiter", "employé"], TaskType.CREATE_EMPLOYEE),
        (["kunde", "customer", "client", "cliente", "kunden"], TaskType.CREATE_CUSTOMER),
        (["prosjekt", "project", "proyecto", "projekt", "projet"], TaskType.CREATE_PROJECT),
        (["produkt", "product", "producto", "produit", "produto"], TaskType.CREATE_PRODUCT),
        (["avdeling", "department", "departamento", "abteilung", "département"], TaskType.CREATE_DEPARTMENT),
    ]
    for keywords, task_type in _LAST_RESORT:
        if any(kw in p for kw in keywords):
            fields = _extract_fields_generic(prompt, task_type)
            fields = _normalize_fields(task_type, fields)
            return TaskClassification(
                task_type=task_type,
                confidence=0.35,
                fields=fields,
                raw_prompt=prompt,
            )
    return TaskClassification(task_type=TaskType.UNKNOWN, confidence=0.0, fields={}, raw_prompt=prompt)


def _classify_with_keywords(
    prompt: str,
    files: Optional[list[dict]] = None,
) -> TaskClassification:
    """Classify task using keyword matching — no LLM required.

    Checks each task type's keyword list against the lowercased prompt,
    respects anti_keywords, and returns the best match.
    """
    prompt_lower = prompt.lower()
    best_type = TaskType.UNKNOWN
    best_score = 0  # longest keyword match (chars) as tiebreaker
    best_hits = 0

    for task_type, pattern in _TASK_PATTERNS.items():
        keywords = pattern.get("keywords", [])
        anti_keywords = pattern.get("anti_keywords", [])

        # Count keyword hits and track the longest matching keyword
        hits = 0
        longest = 0
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in prompt_lower:
                hits += 1
                longest = max(longest, len(kw))
            else:
                # Fallback: check if ALL words of the keyword appear in the prompt
                kw_words = kw_lower.split()
                if len(kw_words) >= 2 and all(w in prompt_lower for w in kw_words):
                    hits += 1
                    longest = max(longest, len(kw) // 2)  # lower score than exact
        if hits == 0:
            continue

        # Check anti-keywords
        anti_hits = sum(1 for ak in anti_keywords if ak.lower() in prompt_lower)
        if anti_hits > 0:
            continue

        # Score: prefer more hits, then longer keyword match (more specific)
        score = (hits, longest)
        if score > (best_hits, best_score):
            best_hits = hits
            best_score = longest
            best_type = task_type

    # Post-hoc disambiguation: if we matched create_project but the prompt also
    # mentions a customer, upgrade to project_with_customer
    if best_type == TaskType.CREATE_PROJECT:
        cust_keywords = ["kunde", "customer", "client", "cliente", "kunden"]
        if any(ck in prompt_lower for ck in cust_keywords):
            best_type = TaskType.PROJECT_WITH_CUSTOMER

    # If we matched create_invoice but the prompt says "for customer X" and no
    # explicit "new customer" / "opprett kunde", treat as invoice_existing_customer
    # (The Gemini prompt handles this, but for keywords we default to create_invoice
    # which is safe — the executor will search for or create the customer.)

    # Last resort: single-word heuristic — NEVER return UNKNOWN if there's any signal
    if best_type == TaskType.UNKNOWN:
        _LAST_RESORT = [
            (["dimensjon", "dimension", "buchhaltungsdimension", "kostsenter", "kostenstelle", "cost center", "fri dimensjon"], TaskType.CREATE_DIMENSION_VOUCHER),
            (["lønn", "lonn", "payroll", "paie", "gehalt", "nómina", "salaire", "lønnskjøring", "lonnskjoring", "salary"], TaskType.RUN_PAYROLL),
            (["leverandørfaktura", "leverandorfaktura", "inngående faktura", "eingangsrechnung", "supplier invoice"], TaskType.CREATE_SUPPLIER_INVOICE),
            (["leverandør", "supplier", "fournisseur", "lieferant", "lieferanten", "proveedor", "fornecedor"], TaskType.CREATE_SUPPLIER),
            (["reverser", "reverse payment", "tilbakefør", "stornere", "bounced", "rückbuchung", "returnert av banken"], TaskType.REVERSE_PAYMENT),
            (["årsavslutning", "arsavslutning", "aarsavslutning", "årsoppgjør", "year-end", "year.end", "arsslutt", "jahresabschluss"], TaskType.YEAR_END_CLOSING),
            (["aktiver modul", "enable module", "slaa paa modul", "activate module", "aktiver modul"], TaskType.ENABLE_MODULE),
            (["faktura", "invoice", "factura", "rechnung", "facture", "fatura"], TaskType.CREATE_INVOICE),
            (["ansatt", "tilsett", "employee", "empleado", "mitarbeiter", "employé", "funcionário", "empregado"], TaskType.CREATE_EMPLOYEE),
            (["kunde", "customer", "client", "cliente", "kunden"], TaskType.CREATE_CUSTOMER),
            (["avdeling", "department", "abteilung", "département", "departamento"], TaskType.CREATE_DEPARTMENT),
            (["prosjekt", "project", "projet", "proyecto", "projeto"], TaskType.CREATE_PROJECT),
            (["produkt", "product", "produit", "producto", "produto"], TaskType.CREATE_PRODUCT),
            (["timer", "hours", "timesheet", "timeliste", "stunden", "heures"], TaskType.LOG_HOURS),
            (["reiseregning", "reiserekning", "travel expense", "reisekosten", "frais de voyage"], TaskType.CREATE_TRAVEL_EXPENSE),
            (["kontakt", "contact", "contacto", "contato"], TaskType.CREATE_CONTACT),
        ]
        for words, fallback_type in _LAST_RESORT:
            if any(w in prompt_lower for w in words):
                best_type = fallback_type
                best_hits = 1
                break

    # Confidence based on hit count
    if best_hits >= 3:
        confidence = 0.85
    elif best_hits >= 2:
        confidence = 0.75
    elif best_hits >= 1:
        confidence = 0.60
    else:
        confidence = 0.0

    # Extract fields
    fields = _extract_fields_generic(prompt, best_type) if best_type != TaskType.UNKNOWN else {}

    # Normalize fields (same as Gemini path)
    fields = _normalize_fields(best_type, fields)

    return TaskClassification(
        task_type=best_type,
        confidence=confidence,
        fields=fields,
        raw_prompt=prompt,
    )
