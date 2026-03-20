"""Tripletex AI Accounting Agent — NM i AI 2026 competition endpoint.

Supports three LLM modes:
  1. Vertex AI Gemini (Cloud Run production) — when GEMINI_MODEL is set
  2. Anthropic Claude (local dev) — when ANTHROPIC_API_KEY is set
  3. Rule-based fallback (no LLM) — when neither is set
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from task_types import TaskClassification, TaskType, TASK_TYPE_DESCRIPTIONS, TASK_FIELD_SPECS
from tripletex_client import TripletexClient

# Structured JSON logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("tripletex-agent")


def log(severity: str, message: str, **extra):
    """Emit structured JSON log compatible with Cloud Run / Cloud Logging."""
    entry = {"severity": severity, "message": message, **extra}
    print(json.dumps(entry), flush=True)


# ---------------------------------------------------------------------------
# Detect LLM mode
# ---------------------------------------------------------------------------

LLM_MODE = "none"
if os.environ.get("GEMINI_MODEL") or os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"):
    LLM_MODE = "gemini"
elif os.environ.get("ANTHROPIC_API_KEY"):
    LLM_MODE = "claude"

log("INFO", f"Starting Tripletex Agent — LLM mode: {LLM_MODE}")

_request_counter = 0


# ---------------------------------------------------------------------------
# Claude-based classifier (local dev)
# ---------------------------------------------------------------------------

_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _build_classifier_prompt() -> str:
    """Build the task-type section for the classifier system prompt."""
    lines = []
    for tt in TaskType:
        desc = TASK_TYPE_DESCRIPTIONS.get(tt, "")
        spec = TASK_FIELD_SPECS.get(tt, {})
        required = spec.get("required", [])
        optional = spec.get("optional", [])
        lines.append(f"- {tt.value}: {desc}")
        if required:
            lines.append(f"  Required: {', '.join(required)}")
        if optional:
            lines.append(f"  Optional: {', '.join(optional)}")
    return "\n".join(lines)


CLASSIFIER_SYSTEM = f"""\
You are an accounting task classifier for Tripletex ERP.
Given a task in ANY language (nb, nn, en, es, pt, de, fr), output JSON:
{{"task_type":"...","confidence":0.0-1.0,"fields":{{...}}}}

TASK TYPES:
{_build_classifier_prompt()}

EXTRACTION RULES:
- Dates → YYYY-MM-DD. Numbers → plain decimals, no thousand separators.
- Entity names must be CLEAN — never include prices, emails, numbers, or descriptors.
  "til 2500 kr", "with email X", "med nummer N" → extract as SEPARATE fields.
- first_name/last_name: split the person's name. "Emma Wilson" → first_name="Emma", last_name="Wilson".
- "til/at/for/à/zu/por" before a price = unit_price, NOT part of the name.
- lines: always an array of objects with description, quantity (default 1), unit_price.
  "3 stk X til 500 kr" → {{"description":"X","quantity":3,"unit_price":500.0}}
- customer_identifier/employee_identifier: use the name, number, or email given to look up.
- contact: "kontaktperson X Y for/hos kunde Z" → first_name="X", last_name="Y", customer_identifier="Z"
- invoice_identifier: invoice number, customer name, or "siste faktura"/"last invoice".
- travel expense: employee_identifier is the employee name/number. title=trip description.
- department_number/employee_number: extract numeric codes separately from names.

LANGUAGE HINTS:
- nb/nn: opprett=create, avdeling=department, avdelingsnummer=department_number, kunde=customer,
  ansatt=employee, faktura=invoice, reiseregning=travel_expense, prosjekt=project,
  slett=delete, oppdater=update, kontaktperson=contact, betaling=payment, kreditnota=credit_note
- de: Erstellen=create, Abteilung=department, Abteilungsnummer=department_number, Mitarbeiter=employee
- fr: Créer=create, département=department, numéro=number, employé=employee
- es: Crear=create, departamento=department, empleado=employee, cliente=customer
- pt: Criar=create, departamento=department, empregado=employee

EXAMPLES (learn the pattern — names are CLEAN, numbers/prices are separate fields):

Input: "Opprett avdeling Markedsføring med avdelingsnummer 40"
Output: {{"task_type":"create_department","confidence":0.95,"fields":{{"name":"Markedsføring","department_number":"40"}}}}

Input: "Créer département Finance numéro 90"
Output: {{"task_type":"create_department","confidence":0.95,"fields":{{"name":"Finance","department_number":"90"}}}}

Input: "Create customer Nordfjord Consulting AS, email post@nordfjord.no, org 987654321"
Output: {{"task_type":"create_customer","confidence":0.95,"fields":{{"name":"Nordfjord Consulting AS","email":"post@nordfjord.no","organization_number":"987654321"}}}}

Input: "Opprett kunde Fjord Shipping AS med e-post kontakt@fjord.no"
Output: {{"task_type":"create_customer","confidence":0.95,"fields":{{"name":"Fjord Shipping AS","email":"kontakt@fjord.no"}}}}

Input: "Opprett en ansatt med fornavn Kari og etternavn Hansen, e-post kari@test.no"
Output: {{"task_type":"create_employee","confidence":0.95,"fields":{{"first_name":"Kari","last_name":"Hansen","email":"kari@test.no"}}}}

Input: "Erstellen Sie einen Mitarbeiter namens Hans Müller"
Output: {{"task_type":"create_employee","confidence":0.95,"fields":{{"first_name":"Hans","last_name":"Müller"}}}}

Input: "Opprett produkt Frakttjeneste til 2500 kr"
Output: {{"task_type":"create_product","confidence":0.95,"fields":{{"name":"Frakttjeneste","price_excluding_vat":2500.0}}}}

Input: "Lag faktura til kunde Hansen AS: 3 stk Frakttjeneste til 2500 kr, 1 stk Emballasje til 150 kr"
Output: {{"task_type":"create_invoice","confidence":0.95,"fields":{{"customer_name":"Hansen AS","lines":[{{"description":"Frakttjeneste","quantity":3,"unit_price":2500.0}},{{"description":"Emballasje","quantity":1,"unit_price":150.0}}]}}}}

Input: "Faktura for kunde Acme Corp med 5 pcs Widget at 100 NOK"
Output: {{"task_type":"invoice_existing_customer","confidence":0.95,"fields":{{"customer_identifier":"Acme Corp","lines":[{{"description":"Widget","quantity":5,"unit_price":100.0}}]}}}}

Input: "Opprett kontaktperson Erik Berg for kunde Aker Solutions, e-post erik@aker.no"
Output: {{"task_type":"create_contact","confidence":0.95,"fields":{{"first_name":"Erik","last_name":"Berg","customer_identifier":"Aker Solutions","email":"erik@aker.no"}}}}

Input: "Oppdater ansatt Kari Hansen med ny telefon 99887766"
Output: {{"task_type":"update_employee","confidence":0.95,"fields":{{"employee_identifier":"Kari Hansen","first_name":"Kari","last_name":"Hansen","phone":"99887766"}}}}

Input: "Slett prosjekt Nettside Redesign"
Output: {{"task_type":"delete_project","confidence":0.95,"fields":{{"project_identifier":"Nettside Redesign"}}}}

Input: "Registrer reiseregning for ansatt Ola Nordmann, tittel Kundebesøk Oslo"
Output: {{"task_type":"create_travel_expense","confidence":0.95,"fields":{{"employee_identifier":"Ola Nordmann","title":"Kundebesøk Oslo"}}}}

If unsure, use "unknown" with confidence 0.0.
Respond with ONLY a JSON object, no markdown."""


async def _classify_with_claude(prompt: str, files: Optional[list[dict]] = None) -> TaskClassification:
    """Classify using Anthropic Claude API."""
    client = _get_anthropic_client()
    user_message = prompt
    if files:
        file_names = [f.get("name", f.get("filename", "unnamed")) for f in files]
        user_message += f"\n\n[Attached files: {', '.join(file_names)}]"

    try:
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=1024,
            temperature=0.0,
            system=CLASSIFIER_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw_text.startswith("```"):
            text_lines = raw_text.split("\n")
            if text_lines[0].startswith("```"):
                text_lines = text_lines[1:]
            if text_lines and text_lines[-1].strip() == "```":
                text_lines = text_lines[:-1]
            raw_text = "\n".join(text_lines)

        data = json.loads(raw_text)
        task_type_str = data.get("task_type", "unknown")
        try:
            task_type = TaskType(task_type_str)
        except ValueError:
            task_type = TaskType.UNKNOWN

        return TaskClassification(
            task_type=task_type,
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
            fields=data.get("fields", {}),
            raw_prompt=prompt,
        )
    except Exception as e:
        log("ERROR", "Claude classification failed", error=str(e))
        return TaskClassification(task_type=TaskType.UNKNOWN, confidence=0.0, fields={}, raw_prompt=prompt)


# ---------------------------------------------------------------------------
# Rule-based classifier (no LLM fallback)
# ---------------------------------------------------------------------------

_KEYWORD_MAP = [
    # --- Enable Module (MUST come before travel — "Aktiver modul Reiseregning" must not match travel) ---
    (TaskType.ENABLE_MODULE, [r"\b(aktiver|enable|aktivieren|activer|activar|ativar|activate)\w*\b.*\b(modul|module|módulo)\b",
                               r"\bslå\s+på\b.*\b(modul|module)\b",
                               r"\b(activar|ativar|activate)\b.*\b(módulo|module|modul)\b"]),
    # --- T3: Bank / Year-end / Error (before travel/employee to catch compound words) ---
    (TaskType.BANK_RECONCILIATION, [r"\bbankavstem\w*\b",
                                     r"\bbank\w*\b.*\bavstem\w*\b",
                                     r"\bavstem\w*\b.*\bbank\w*\b",
                                     r"\b(reconcil|abgleich|rapprochement)\w*\b"]),
    (TaskType.ERROR_CORRECTION, [r"\b(korriger|correct|fiks|fix)\w*\b.*\b(feil|error|bilag|voucher|postering)\b",
                                   r"\b(feil|error)\w*\b.*\b(korriger|correct|rett)\b"]),
    (TaskType.YEAR_END_CLOSING, [r"\bårsavslut\w*\b", r"\bårsoppgjør\w*\b",
                                   r"\byear.?end\b", r"\bjahresabschluss\w*\b", r"\bclôture\b",
                                   r"\b(avslutt|close|lukk)\w*\b.*\b(år|year|regnskapsår)\w*\b"]),
    # --- Travel (after enable_module — "reiseregning" alone should match travel) ---
    # NOTE: "reise" without trailing \b so it matches "reiseregning" as substring
    (TaskType.DELETE_TRAVEL_EXPENSE, [r"\b(slett|delete|remove|fjern|löschen|eliminar|supprimer)\b.*\b(reise|travel|viaje|voyage|reisekostenabrechnung)",
                                       r"\b(slett|delete|remove|fjern)\b.*\b(?:reiseregning|reiserekning)\b"]),
    (TaskType.CREATE_TRAVEL_EXPENSE, [r"\breiseregning\b", r"\breiserekning\b",
                                       r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar)\b.*\b(reise|travel|viaje|voyage|reisekostenabrechnung)\b"]),
    # --- Employee ---
    (TaskType.DELETE_EMPLOYEE, [r"\b(slett|fjern|delete|remove|löschen|entfernen|eliminar|supprimer|excluir)\b.*\b(ansatt|tilsett|employee|empleado|mitarbeiter|employé|funcionário|empregado)\b"]),
    (TaskType.UPDATE_EMPLOYEE, [r"\b(oppdater|endre|update|modify|ändra|aktualisieren|ändern|actualizar|modificar|modifier|atualizar)\b.*\b(ansatt|tilsett|employee|empleado|mitarbeiter|employé|empregado)\b"]),
    (TaskType.SET_EMPLOYEE_ROLES, [r"\b(rolle|role|access|tilgang|user.?type)\b.*\b(ansatt|tilsett|employee)\b",
                                    r"\b(ansatt|employee)\b.*\b(rolle|role|access|tilgang)\b",
                                    r"\b(sett|set|gi|give|assign)\b.*\b(ansatt|employee)\b.*\b(som|as|to)\s+\w+"]),
    (TaskType.CREATE_EMPLOYEE, [r"\b(opprett|lag|create|add|erstellen|créer|crear|criar|register|registrer|legg\s+til)\b.*\b(ansatt|tilsett|employee|empleado|mitarbeiter|employé|funcionário|empregado)\b",
                                r"\bny\w?\b.*\b(ansatt|tilsett|employee|empleado|mitarbeiter|employé)\b",
                                r"\b(ansatt|tilsett|employee)\b.*\b(som\s+heter|named?|called)\b",
                                r"\b(ansatt|tilsett|employee)\b.*\b(fornavn|first.?name|etternavn|last.?name)\b"]),
    # --- Invoice (MUST come before customer to avoid "opprett faktura for kunde" → CREATE_CUSTOMER) ---
    (TaskType.CREATE_CREDIT_NOTE, [r"\b(kreditnota|credit.?note|gutschrift|avoir|nota de crédito)\b"]),
    (TaskType.INVOICE_WITH_PAYMENT, [r"\b(faktura|invoice|factura|rechnung|facture)\b.*\b(betaling|payment|betalt|paid|pago|zahlung|paiement)\b",
                                     r"\b(facture|faktura|invoice|rechnung)\s+impayée?\b.*\b(enregistr|registr|betaling|payment|paiement)\b",
                                     r"\b(unbezahlte|impayée?|unpaid)\b.*\b(rechnung|facture|invoice|faktura)\b.*\b(zahlung|paiement|payment|betaling)\b"]),
    (TaskType.REGISTER_PAYMENT, [r"\b(registrer|register)\b.*\b(betaling|innbetaling|payment|pago)\b",
                                  r"\b(betaling|payment)\b.*\b(faktura|invoice)\b"]),
    (TaskType.INVOICE_EXISTING_CUSTOMER, [r"\b(faktura|invoice|factura|rechnung)\b.*\b(kund(?:e|en)|customer|client|cliente)\b",
                                          r"\b(faktura|invoice)\b\s+(?:til|to|for|an)\s+[A-ZÆØÅ]",
                                          r"\bfaktur\w*\b.*\b(kund(?:e|en)|customer|client|cliente)\b"]),
    (TaskType.CREATE_INVOICE, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar)\b.*\b(faktura|invoice|factura|rechnung|facture|fatura)\b",
                                r"\b(faktura|invoice|factura|rechnung|facture|fatura)\b"]),
    # --- Contact (use "kontaktperson" not bare "kontakt" to avoid matching email addresses like kontakt@...) ---
    (TaskType.UPDATE_CONTACT, [r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\b(kontaktperson|contact(?!@)|contacto|contato)\b"]),
    (TaskType.CREATE_CONTACT, [r"\bkontaktperson\b", r"\b(opprett|create|add|erstellen|créer|crear|criar)\b.*\b(contactperson|contact(?!@)|contacto|contato)\b"]),
    # --- Project (before customer — "prosjekt for kunde" should match project, not customer) ---
    (TaskType.PROJECT_WITH_CUSTOMER, [r"\bprosjekt\w*\b.*\b(kund(?:e|en)|customer|client|cliente)\b",
                                      r"\b(project|proyecto|projekt|projet)\b.*\b(kund(?:e|en)|customer|client|cliente)\b",
                                      r"\bprosjekt\w*\b.*\bknytt\s+til\b",
                                      r"\b(project|proyecto|projekt|projet)\b.*\bknytt\s+til\b"]),
    (TaskType.DELETE_PROJECT, [r"\b(slett|delete|remove|löschen|eliminar|supprimer)\b.*\bprosjekt\w*\b",
                                r"\b(slett|delete|remove|löschen|eliminar|supprimer)\b.*\b(project|proyecto|projekt|projet)\b"]),
    (TaskType.UPDATE_PROJECT, [r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\bprosjekt\w*\b",
                                r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\b(project|proyecto|projekt|projet)\b"]),
    (TaskType.CREATE_PROJECT, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar|registrer|register|legg\s+til|add|set\s+up)\b.*\bprosjekt\w*\b",
                                r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar|registrer|register|legg\s+til|add|set\s+up)\b.*\b(project|proyecto|projekt|projet)\b",
                                r"\bny\w?\b.*\bprosjekt\w*\b",
                                r"\bny\w?\b.*\b(project|proyecto|projekt|projet)\b"]),
    # --- Customer (after invoice and project to avoid false matches) ---
    (TaskType.DELETE_CUSTOMER, [r"\b(slett|fjern|delete|remove|löschen|entfernen|eliminar|supprimer|excluir)\b.*\b(kund(?:e|en)|customer|client|cliente)\b"]),
    (TaskType.UPDATE_CUSTOMER, [r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\b(kund(?:e|en)|customer|client|cliente)\b"]),
    (TaskType.FIND_CUSTOMER, [r"\b(finn|find|search|søk|suchen|buscar|chercher|procurar)\b.*\b(kund(?:e|en)|customer|client|cliente)\b"]),
    (TaskType.CREATE_CUSTOMER, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar|registrer|register|legg\s+til|add|set\s+up)\b.*\b(kund(?:e|en)|customer|client|cliente)\b",
                                r"\bny\w?\b.*\b(kund(?:e|en)|customer|client|cliente)\b",
                                r"\b(kund(?:e|en)|customer|client|cliente)\b.*\b(opprett|create|lag)\b"]),
    # --- Product / Department ---
    (TaskType.CREATE_PRODUCT, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar|registrer|register|legg\s+til|add)\b.*\b(produkt|product|producto|produit|produto)\b",
                                r"\bny\w?\b.*\b(produkt|product|producto|produit|produto)\b"]),
    (TaskType.UPDATE_DEPARTMENT, [r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\b(avdeling|department|departamento|abteilung|département)\b"]),
    (TaskType.CREATE_DEPARTMENT, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar|registrer|register|legg\s+til|add)\b.*\b(avdeling|department|departamento|abteilung|département)\b",
                                   r"\bny\w?\b.*\b(avdeling|department|departamento|abteilung|département)\b",
                                   r"\b(avdeling|department|departamento|abteilung|département)\b.*\b(opprett|create|lag)\b"]),
    # --- Log Hours / Timesheet ---
    (TaskType.LOG_HOURS, [r"\b(log|logg|registrer|register|føre?|enter|erfassen|enregistrer)\b.*\b(timer|hours?|stunden|heures|horas|tid|time)\b",
                           r"\b(timer|hours?|timesheet|timefør\w*|tidregistrering|timeliste)\b.*\b(prosjekt|project|projekt|projet)\b",
                           r"\b(timesheet|timeliste|timefør\w*|tidregistrering|stundenzettel|feuille.de.temps)\b"]),
    # --- Project Billing ---
    (TaskType.PROJECT_BILLING, [r"\bfaktur\w*\b.*\b(prosjekt|project|projekt|projet)\b",
                                 r"\b(prosjekt|project)\b.*\bfaktur\w*\b"]),
]


def _extract_fields_rule_based(task_type: TaskType, prompt: str) -> dict:
    """Extract fields from prompt using regex patterns. Best-effort for rule-based mode."""
    fields: dict[str, Any] = {}
    text = prompt

    # --- Name patterns (Norwegian + English + multilingual) ---

    # "med navn X" / "named X" / "appelé X" / "namens X" / "chamado X" / "called X" / "kalt X"
    m = re.search(
        r"(?:med\s+namn|med\s+navn|named?|called|kalt|heiter|heter|appelée?|nommée?|namens|genannt|"
        r"chamad[oa]|com\s+nome|llamad[oa]|con\s+nombre)\s+"
        r"(.+?)"
        r"(?:\s*[,.]|\s+(?:og|and|avec|mit|con|com|med|with|und|et|e|y|til|at|for|zu|à|"
        r"nummer|number|numéro|número)\s|$)",
        text, re.I,
    )
    if m:
        fields["name"] = m.group(1).strip().rstrip(".,")

    # "fornavn X og etternavn Y" (Norwegian employee name pattern)
    m = re.search(r"fornavn\s+(\S+)\s+(?:og\s+)?etternavn\s+(\S+)", text, re.I)
    if m:
        fields["first_name"] = m.group(1).rstrip(".,")
        fields["last_name"] = m.group(2).rstrip(".,")

    # "first name X last name Y"
    m = re.search(r"first\s*name\s+(\S+)\s+(?:and\s+)?last\s*name\s+(\S+)", text, re.I)
    if m:
        fields["first_name"] = m.group(1)
        fields["last_name"] = m.group(2)

    # "employee named X Y" / "ansatt med navn X Y" / "som heiter X Y"
    if task_type in (TaskType.CREATE_EMPLOYEE, TaskType.UPDATE_EMPLOYEE, TaskType.DELETE_EMPLOYEE):
        # Pattern 1: "ansatt/employee [named] X Y"
        m = re.search(
            r"(?:ansatt|tilsett|employee|empleado|mitarbeiter|employé|funcionário)\s+"
            r"(?:med\s+navn\s+|named?\s+|called\s+|namens\s+|appelée?\s+|chamad[oa]\s+|kalt\s+)?"
            r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)",
            text,
        )
        if m and "first_name" not in fields:
            fields["first_name"] = m.group(1).rstrip(",.")
            fields["last_name"] = m.group(2).rstrip(",.")

        # Pattern 2: "som heiter/heter X Y" (Nynorsk/Bokmål)
        if "first_name" not in fields:
            m = re.search(
                r"(?:som\s+)?(?:heiter|heter|hedder|heißt|named?|called)\s+"
                r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)",
                text,
            )
            if m:
                fields["first_name"] = m.group(1).rstrip(",.")
                fields["last_name"] = m.group(2).rstrip(",.")

    # Entity-keyword + name (for departments, products, projects without "med navn"/"named")
    # "avdeling HR", "department Finance", "Abteilung Vertrieb", "produkt Widget"
    _NAME_ENTITY_TYPES = (TaskType.CREATE_DEPARTMENT, TaskType.CREATE_PRODUCT,
                          TaskType.CREATE_PROJECT, TaskType.CREATE_CUSTOMER,
                          TaskType.PROJECT_WITH_CUSTOMER, TaskType.FIND_CUSTOMER,
                          TaskType.UPDATE_CUSTOMER, TaskType.UPDATE_PROJECT,
                          TaskType.DELETE_PROJECT)
    if "name" not in fields and task_type in _NAME_ENTITY_TYPES:
        # Try quoted name first: 'prosjektet "Foo Bar"' or "prosjektet 'Foo Bar'"
        m = re.search(
            r"(?i:avdeling\w*|department\w*|département\w*|departamento\w*|abteilung\w*|"
            r"produkt\w*|product\w*|produit\w*|producto\w*|produto\w*|"
            r"prosjekt\w*|project\w*|projet\w*|proyecto\w*|projeto\w*|"
            r"kund(?:e|en)\w*|customer\w*|client\w*|cliente\w*)\s+"
            r"[\"']([^\"']+)[\"']",
            text, re.I,
        )
        if m:
            fields["name"] = m.group(1).strip()
        # Fallback: unquoted name starting with uppercase
        if "name" not in fields:
            m = re.search(
            r"(?i:avdeling|department|département|departamento|abteilung|"
            r"produkt|product|produit|producto|produto|"
            r"prosjekt|project|projet|proyecto|projeto|"
            r"kund(?:e|en)|customer|client|cliente)\s+"
            r"(?i:med\s+(?:navn\s+)?|named?\s+|called\s+|kalt\s+|appelée?\s+|nommée?\s+|"
            r"namens\s+|genannt\s+|chamad[oa]\s+|llamad[oa]\s+)?"
            r"([A-ZÆØÅ\u00C0-\u024F][\w&-]+(?:\s+[A-ZÆØÅ\u00C0-\u024F&][\w&-]+)*)"
            r"(?:\s*[,.]|\s+(?i:og|and|avec|mit|con|com|med|with|und|et|til|at|for|zu|à|"
            r"nummer|number|numéro|número|avdelingsnummer|abteilungsnummer|"
            r"department.?number|e-post|email|telefon|phone|pris|price|start)\b|$)",
            text,
        )
        if m:
            fields["name"] = m.group(1).strip().rstrip(".,")

    # --- Email ---
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    if m:
        fields["email"] = m.group(0)

    # --- Phone ---
    m = re.search(r"(?:telefon|phone|tlf|mobil)\s*:?\s*([\d\s\+\-]+)", text, re.I)
    if m:
        fields["phone"] = m.group(1).strip()

    # --- Department number (only for department tasks to avoid matching org numbers) ---
    if task_type == TaskType.CREATE_DEPARTMENT:
        m = re.search(
            r"(?:avdelingsnummer|department\s*number|abteilungsnummer|"
            r"numéro\s*(?:de\s*)?département|número\s*(?:de\s*)?departamento|"
            r"(?:med|with|mit|og|and|avec|con)\s+(?:nummer|number|Nummer|numéro|número))"
            r"\s*:?\s*(\d+)",
            text, re.I,
        )
        if m:
            fields["department_number"] = m.group(1)

        # Fallback: standalone "numéro/número/nummer/number N"
        if "department_number" not in fields:
            m = re.search(r"(?:numéro|número|nummer|number|nr\.?)\s*:?\s*(\d+)", text, re.I)
            if m:
                fields["department_number"] = m.group(1)

    # --- Price ---
    m = re.search(r"(?:pris|price|prix|Preis|precio|preço)\s*:?\s*(\d+[\d.,]*)\s*(?:kr|NOK|,-)?", text, re.I)
    if m:
        price_str = m.group(1).replace(",", ".").replace(" ", "")
        try:
            fields["price_excluding_vat"] = float(price_str)
        except ValueError:
            pass
    # Also catch "XXX NOK"
    if "price_excluding_vat" not in fields:
        m = re.search(r"(\d+[\d.,]*)\s*(?:kr|NOK)", text, re.I)
        if m:
            price_str = m.group(1).replace(",", ".").replace(" ", "")
            try:
                fields["price_excluding_vat"] = float(price_str)
            except ValueError:
                pass

    # --- VAT percentage ---
    m = re.search(r"(\d+)\s*%\s*(?:MVA|mva|MwSt|Steuersatz|VAT|TVA|IVA|taux|tax)", text, re.I)
    if not m:
        m = re.search(r"(?:MVA|mva|MwSt|Steuersatz|VAT|TVA|IVA|taux|tax)\s*:?\s*(\d+)\s*%?", text, re.I)
    if m:
        fields["vat_percentage"] = int(m.group(1))

    # --- Product number ---
    if task_type == TaskType.CREATE_PRODUCT:
        m = re.search(r"(?:produktnummer|product\s*number|Produktnummer|numéro\s*de\s*produit|número\s*de\s*producto|"
                       r"(?:med|with|mit|og|and|avec|con)\s+(?:nummer|number|Nummer|numéro|número))\s*:?\s*(\d+)", text, re.I)
        if m:
            fields["number"] = m.group(1)
        if "number" not in fields:
            m = re.search(r"(?:nummer|number|nr\.?)\s*:?\s*(\d+)", text, re.I)
            if m:
                fields["number"] = m.group(1)

    # --- Organization number ---
    m = re.search(r"(?:org\.?(?:anisasjonsnummer|\.?\s*nr\.?)?|organization\s*number|Organisationsnummer|nº\s*org\.?|numéro\s*d'organisation|número\s*de\s*organización)\s*:?\s*([\d\-\s]{9,})", text, re.I)
    if m:
        fields["organization_number"] = re.sub(r'[^\d]', '', m.group(1))

    # --- Date of birth ---
    if task_type in (TaskType.CREATE_EMPLOYEE, TaskType.UPDATE_EMPLOYEE):
        m = re.search(r"(?:født|born|date.?of.?birth|fødselsdato|geburtsdatum|fecha.?de.?nacimiento|date.?de.?naissance)\s*:?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
        if m:
            fields["date_of_birth"] = m.group(1)
        else:
            # Parse text dates: "4. May 1986", "15. mars 2026", "geboren am 15. März 1990"
            _MONTH_MAP = {
                "januar": "01", "january": "01", "janvier": "01", "enero": "01", "janeiro": "01", "januar": "01",
                "februar": "02", "february": "02", "février": "02", "febrero": "02", "fevereiro": "02",
                "mars": "03", "march": "03", "mars": "03", "marzo": "03", "março": "03", "märz": "03",
                "april": "04", "avril": "04", "abril": "04",
                "mai": "05", "may": "05", "mai": "05", "mayo": "05", "maio": "05",
                "juni": "06", "june": "06", "juin": "06", "junio": "06", "junho": "06",
                "juli": "07", "july": "07", "juillet": "07", "julio": "07", "julho": "07",
                "august": "08", "août": "08", "agosto": "08",
                "september": "09", "septembre": "09", "septiembre": "09", "setembro": "09",
                "oktober": "10", "october": "10", "octobre": "10", "octubre": "10", "outubro": "10",
                "november": "11", "novembre": "11", "noviembre": "11", "novembro": "11",
                "desember": "12", "december": "12", "décembre": "12", "diciembre": "12", "dezembro": "12", "dezember": "12",
            }
            m = re.search(
                r"(?:født|born|geburtsdatum|geboren|né[e]?|nacido|nascido)[\s:]+(?:am\s+|le\s+)?(\d{1,2})\.?\s+"
                r"([A-Za-zÀ-ÿ]+)\s+(\d{4})",
                text, re.I,
            )
            if m:
                day = int(m.group(1))
                month_str = m.group(2).lower()
                year = m.group(3)
                month = _MONTH_MAP.get(month_str)
                if month:
                    fields["date_of_birth"] = f"{year}-{month}-{day:02d}"

    # --- User type / role (for employees) ---
    if task_type in (TaskType.CREATE_EMPLOYEE, TaskType.SET_EMPLOYEE_ROLES):
        text_lower = text.lower()
        if any(w in text_lower for w in ["kontoadministrator", "administrator", "admin"]):
            fields["user_type"] = "ADMINISTRATOR"
        elif any(w in text_lower for w in ["begrenset", "restricted", "limited"]):
            fields["user_type"] = "NO_ACCESS"
        elif "ingen tilgang" in text_lower or "no access" in text_lower:
            fields["user_type"] = "NO_ACCESS"
        elif "standard" in text_lower:
            fields["user_type"] = "STANDARD"

    # --- Address ---
    if task_type in (TaskType.CREATE_CUSTOMER, TaskType.CREATE_EMPLOYEE, TaskType.UPDATE_CUSTOMER):
        # "adresse Storgata 5, 3015 Drammen" / "address 123 Main St, 0001 Oslo"
        m = re.search(r"(?:adresse|address|Adresse|dirección|endereço|adresse)\s*:?\s*(.+?)(?:\s*[.,]\s*(\d{4,5})\s+(\S+(?:\s+\S+)?))?(?:\s*[.,]|$)", text, re.I)
        if m:
            fields["address_line1"] = m.group(1).strip().rstrip(".,")
            if m.group(2):
                fields["postal_code"] = m.group(2)
            if m.group(3):
                fields["city"] = m.group(3).strip().rstrip(".,")

    # --- Customer name for invoices ---
    if task_type in (TaskType.CREATE_INVOICE, TaskType.INVOICE_EXISTING_CUSTOMER,
                     TaskType.INVOICE_WITH_PAYMENT, TaskType.PROJECT_BILLING):
        # "for kunde X", "til kunde X", "for customer X"
        # Stop at punctuation, "med N stk", "with N", digits followed by "stk/pcs"
        m = re.search(r"(?:til\s+|for\s+)?(?:kund(?:e|en)|customer|client|cliente|Kunde|Client)\s+(.+?)(?:\s*[.,:\s]*:\s*|\s*[.,]\s*|\s+med\s+\d|\s+with\s+\d|\s+for\s+\d|\s+\d+\s*(?:stk|pcs|x|timer|hours?)\b|\s*$)", text, re.I)
        if m:
            fields["customer_name"] = m.group(1).strip().rstrip(".,:")
        # Fallback: "faktura til X:" / "Lag faktura til X:" (no kunde/customer keyword)
        if "customer_name" not in fields:
            m = re.search(r"(?:faktura|invoice|factura|rechnung|facture|fatura)\s+(?:til|for|to|für|pour|para|per)\s+(.+?)(?:\s*:\s*|\s*[.,]\s*|\s+med\s+\d|\s+with\s+\d|\s+for\s+\d|\s+\d+\s*(?:stk|pcs|x|timer|hours?)\b|\s*$)", text, re.I)
            if m:
                fields["customer_name"] = m.group(1).strip().rstrip(".,:")

    # --- Invoice line extraction ---
    if task_type in (TaskType.CREATE_INVOICE, TaskType.INVOICE_EXISTING_CUSTOMER,
                     TaskType.INVOICE_WITH_PAYMENT, TaskType.PROJECT_BILLING):
        lines = _extract_invoice_lines(text)
        if lines:
            fields["lines"] = lines

    # --- Travel expense fields ---
    if task_type in (TaskType.CREATE_TRAVEL_EXPENSE, TaskType.DELETE_TRAVEL_EXPENSE):
        # Employee identifier: "for ansatt X Y" / "for employee X Y"
        m = re.search(
            r"(?:for\s+)?(?:ansatt|tilsett|employee|mitarbeiter|employé|empleado)\s+"
            r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)",
            text,
        )
        if m:
            fields["first_name"] = m.group(1).rstrip(",.")
            fields["last_name"] = m.group(2).rstrip(",.")
            fields["employee_identifier"] = f"{fields['first_name']} {fields['last_name']}"
        # Title: "reiseregning TITLE for ansatt" / "tittel TITLE" / "title TITLE"
        m = re.search(r"(?:tittel|title)\s+(.+?)(?:\s*[,.]|\s+(?:for|hos)\s|$)", text, re.I)
        if m:
            fields["title"] = m.group(1).strip().rstrip(",.")
        elif not fields.get("title"):
            # "Reiseregning TITLE for ansatt X" — capture text between reiseregning and "for ansatt"
            m = re.search(
                r"[Rr]eise(?:regning|rekning)\s+(.+?)\s+(?:for\s+(?:ansatt|tilsett|employee)|$)",
                text,
            )
            if m:
                fields["title"] = m.group(1).strip().rstrip(",.")
            else:
                # "travel expense TITLE" or "reiseregning TITLE"
                m = re.search(
                    r"(?:reiseregning|reiserekning|travel\s*expense|reisekostenabrechnung|note\s*de\s*frais)\s+(.+?)(?:\s*[,.]|$)",
                    text, re.I,
                )
                if m:
                    title_candidate = m.group(1).strip().rstrip(",.")
                    # Skip if title is just "for ansatt X" (employee ref, not a title)
                    if not re.match(r"^for\s+(?:ansatt|tilsett|employee|mitarbeiter|employé|empleado)", title_candidate, re.I):
                        fields["title"] = title_candidate

    # --- Contact person extraction ---
    if task_type == TaskType.CREATE_CONTACT:
        # "kontaktperson Per Olsen" / "contact person John Doe"
        if "first_name" not in fields:
            m = re.search(
                r"(?:kontaktperson|contact\s*person|contacto|contato|kontakt)\s+"
                r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)",
                text,
            )
            if m:
                fields["first_name"] = m.group(1).rstrip(",.")
                fields["last_name"] = m.group(2).rstrip(",.")
        # Customer reference: "for/hos kunde X" / "for customer X"
        if "customer_name" not in fields and "customer_identifier" not in fields:
            m = re.search(
                r"(?:for|hos|bei|pour|para|per)\s+(?:kund(?:e|en)|customer|client|cliente|Kunde)\s+"
                r"(.+?)(?:\s*[,.]|$)",
                text, re.I,
            )
            if m:
                fields["customer_identifier"] = m.group(1).strip().rstrip(",.")

    # --- Project with customer: extract customer_name separately ---
    if task_type in (TaskType.PROJECT_WITH_CUSTOMER, TaskType.CREATE_PROJECT):
        if "customer_name" not in fields:
            m = re.search(
                r"(?:for|hos|til|bei|pour|para|knytt\s+til)\s+(?:kund(?:e|en)|customer|client|cliente|Kunde)\s+"
                r"(.+?)(?:\s*[,.]|\s+(?:start|med|with|og|and|org)\s|\s*\(|$)",
                text, re.I,
            )
            if m:
                fields["customer_name"] = m.group(1).strip().rstrip(",.")
        # Extract start date: "start YYYY-MM-DD" or "startdato YYYY-MM-DD"
        m = re.search(r"(?:start(?:dato)?|begin)\s+(\d{4}-\d{2}-\d{2})", text, re.I)
        if m:
            fields["start_date"] = m.group(1)
        # Extract project manager: "Prosjektleiar/Prosjektleder/Project manager er/is X Y"
        if "project_manager_name" not in fields:
            m = re.search(
                r"(?:prosjektlei(?:ar|er|der)|project\s*manager|projektleiter|chef\s*de\s*projet|jefe\s*de\s*proyecto)"
                r"\s+(?:er|is|ist|est|es|será)?\s*"
                r"([A-ZÆØÅ\u00C0-\u024F]\S+\s+[A-ZÆØÅ\u00C0-\u024F]\S+)",
                text, re.I,
            )
            if m:
                fields["project_manager_name"] = m.group(1).strip().rstrip(",.")
                # Check for email in parentheses right after the name
                name_end = m.end()
                rest = text[name_end:]
                em = re.match(r"\s*\(([^)]+@[^)]+)\)", rest)
                if em:
                    fields["project_manager_email"] = em.group(1).strip()

    # --- Invoice identifier (for payment, credit note, and invoice-related tasks) ---
    _INVOICE_TASK_TYPES = (TaskType.REGISTER_PAYMENT, TaskType.CREATE_CREDIT_NOTE,
                           TaskType.INVOICE_WITH_PAYMENT)
    if task_type in _INVOICE_TASK_TYPES:
        # "faktura 12345" / "invoice 12345" / "factura 12345" / "Rechnung 12345"
        m = re.search(
            r"(?:faktura|invoice|factura|Rechnung|facture)\s+(?:nummer|number|numéro|nr\.?|#)?\s*#?(\d+)",
            text, re.I,
        )
        if m:
            fields["invoice_id"] = m.group(1)
        # Amount: "beløp 1500 kr" / "amount 1500" / "betrag 1500" / "montant 1500"
        m = re.search(
            r"(?:beløp|amount|betrag|montant|monto|importe|valor)\s+(\d+[\d.,]*)\s*(?:kr|NOK|,-)?",
            text, re.I,
        )
        if m:
            amt_str = m.group(1).replace(",", ".").replace(" ", "")
            try:
                fields["amount"] = float(amt_str)
            except ValueError:
                pass
        # Also catch standalone "N kr/NOK" if no amount yet
        if "amount" not in fields:
            m = re.search(r"(\d+[\d.,]*)\s*(?:kr|NOK)", text, re.I)
            if m:
                amt_str = m.group(1).replace(",", ".").replace(" ", "")
                try:
                    fields["amount"] = float(amt_str)
                except ValueError:
                    pass

    # --- T3 field extraction ---
    if task_type == TaskType.YEAR_END_CLOSING:
        m = re.search(r"\b(20\d{2})\b", text)
        if m:
            fields["year"] = m.group(1)

    if task_type == TaskType.ENABLE_MODULE:
        m = re.search(r"(?:modul|module|funksjon|feature)\s+(.+?)(?:\s*[,.]|$)", text, re.I)
        if m:
            fields["module_name"] = m.group(1).strip()

    if task_type == TaskType.BANK_RECONCILIATION:
        # Extract account number: "konto 1920" / "account 1920"
        m = re.search(r"(?:konto|account|Konto|compte|cuenta)\s*:?\s*(\d+)", text, re.I)
        if m:
            fields["account_number"] = m.group(1)
        # Extract period: "mars 2026" / "March 2026" / "2026-03"
        m = re.search(r"(?:for\s+)?(?:januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember|"
                      r"january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})", text, re.I)
        if m:
            fields["period"] = m.group(0).strip()

    if task_type == TaskType.ERROR_CORRECTION:
        m = re.search(r"(?:bilag|voucher|postering|posting)\s*(?:nr\.?\s*)?(\d+)", text, re.I)
        if m:
            fields["voucher_identifier"] = m.group(1)

    if task_type == TaskType.LOG_HOURS:
        # Extract hours: "27 hours" / "27 timer"
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:timer|hours?|stunden|heures|horas|t)\b", text, re.I)
        if m:
            fields["hours"] = float(m.group(1).replace(",", "."))
        # Extract project name: 'project "System Upgrade"' or 'prosjekt Alpha'
        m = re.search(r"(?:prosjekt|project|projekt|projet)\s+[\"']([^\"']+)[\"']", text, re.I)
        if m:
            fields["project_name"] = m.group(1).strip()
        elif not fields.get("project_name"):
            m = re.search(r"(?:prosjekt|project|projekt|projet)\s+([A-ZÆØÅ\u00C0-\u024F][\w\s-]+?)(?:\s*[,.]|\s+(?:for|med|with|til|on)\s|$)", text, re.I)
            if m:
                fields["project_name"] = m.group(1).strip()
        # Extract activity name: 'activity "Rådgivning"' or 'aktivitet Konsultering'
        m = re.search(r"(?:activity|aktivitet|Aktivität|activité|actividad)\s+[\"']([^\"']+)[\"']", text, re.I)
        if m:
            fields["activity_name"] = m.group(1).strip()
        elif not fields.get("activity_name"):
            m = re.search(r"(?:activity|aktivitet|Aktivität|activité|actividad)\s+([A-ZÆØÅ\u00C0-\u024F][\w\s-]+?)(?:\s*[,.]|\s+(?:for|in|i|on|med|with)\s|$)", text, re.I)
            if m:
                fields["activity_name"] = m.group(1).strip()
        # Extract employee: "for Emily Smith" / "for ansatt X Y"
        m = re.search(
            r"(?:for|av|by|von|par|por)\s+(?:ansatt\s+|tilsett\s+|employee\s+)?"
            r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)",
            text,
        )
        if m:
            fields["first_name"] = m.group(1).rstrip(",.")
            fields["last_name"] = m.group(2).rstrip(",.")
            fields["employee_identifier"] = f"{fields['first_name']} {fields['last_name']}"
        # Extract employee email
        m = re.search(r"\(([^)]+@[^)]+)\)", text)
        if m:
            fields["employee_email"] = m.group(1).strip()
            if not fields.get("email"):
                fields["email"] = fields["employee_email"]
        # Extract date
        m = re.search(r"(?:date|dato|Datum|date|fecha)\s*:?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
        if m:
            fields["date"] = m.group(1)

    # --- Delete customer: extract customer name ---
    if task_type == TaskType.DELETE_CUSTOMER:
        m = re.search(
            r"(?:kund(?:e|en)|customer|client|cliente|Kunde)\s+"
            r"(.+?)(?:\s*[,.]|$)",
            text, re.I,
        )
        if m:
            fields["customer_identifier"] = m.group(1).strip().rstrip(",.")

    # --- Update contact: extract contact + customer ---
    if task_type == TaskType.UPDATE_CONTACT:
        # Contact name: "kontaktperson X Y" / "contact X Y"
        m = re.search(
            r"(?:kontaktperson|contact\s*person|contacto|contato|kontakt)\s+"
            r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)",
            text,
        )
        if m:
            fields["first_name"] = m.group(1).rstrip(",.")
            fields["last_name"] = m.group(2).rstrip(",.")
            fields["contact_identifier"] = f"{fields['first_name']} {fields['last_name']}"
        # Customer reference
        m = re.search(
            r"(?:for|hos|bei|pour|para|per)\s+(?:kund(?:e|en)|customer|client|cliente|Kunde)\s+"
            r"(.+?)(?:\s*[,.]|$)",
            text, re.I,
        )
        if m:
            fields["customer_identifier"] = m.group(1).strip().rstrip(",.")

    # --- Update department: extract department name ---
    if task_type == TaskType.UPDATE_DEPARTMENT:
        m = re.search(
            r"(?:avdeling|department|département|departamento|abteilung)\s+"
            r"(.+?)(?:\s*[,.]|\s+(?:med|with|mit|og|and|avec|con|til|to)\s|$)",
            text, re.I,
        )
        if m:
            fields["department_identifier"] = m.group(1).strip().rstrip(",.")
        # New name
        m = re.search(
            r"(?:nytt?\s+(?:navn|name|Namn)|new\s+name|neuer?\s+Name|nouveau\s+nom|nuevo\s+nombre|novo\s+nome)\s+(.+?)(?:\s*[,.]|$)",
            text, re.I,
        )
        if m:
            fields["new_name"] = m.group(1).strip().rstrip(",.")

    if task_type == TaskType.PROJECT_BILLING:
        # Extract project name
        m = re.search(r"(?:prosjekt|project|projekt|projet)\s+(.+?)(?:\s*[,.]|\s+(?:med|with|for|til)\s|$)", text, re.I)
        if m:
            fields["project_identifier"] = m.group(1).strip()

    # --- Set employee roles ---
    if task_type == TaskType.SET_EMPLOYEE_ROLES:
        # Extract employee name: "ansatt X Y" / "employee X Y" / "employee role for X Y"
        if "first_name" not in fields:
            m = re.search(
                r"(?:ansatt|tilsett|employee|mitarbeiter|employé|empleado)\s+"
                r"(?:role\s+)?(?:for\s+)?"
                r"([A-ZÆØÅ\u00C0-\u024F0-9]\S+)\s+([A-ZÆØÅ\u00C0-\u024F0-9]\S+)",
                text,
            )
            if m:
                fields["first_name"] = m.group(1).rstrip(",.")
                fields["last_name"] = m.group(2).rstrip(",.")
                fields["employee_identifier"] = f"{fields['first_name']} {fields['last_name']}"
        # Extract user type: "som administrator" / "as STANDARD" / "to EXTENDED" / "tilgang som X"
        m = re.search(
            r"(?:som|as|to|til)\s+(administrator|standard|extended|no.?access|begrenset|limited)",
            text, re.I,
        )
        if m:
            role_raw = m.group(1).upper().replace(" ", "_").replace("-", "_")
            # Map Norwegian/common terms to Tripletex user types (valid: STANDARD, EXTENDED, NO_ACCESS)
            role_map = {
                "ADMINISTRATOR": "EXTENDED",  # Tripletex has no "admin" — EXTENDED is highest
                "ADMIN": "EXTENDED",
                "STANDARD": "STANDARD",
                "EXTENDED": "EXTENDED",
                "NO_ACCESS": "NO_ACCESS",
                "NOACCESS": "NO_ACCESS",
                "BEGRENSET": "NO_ACCESS",
                "LIMITED": "NO_ACCESS",
            }
            fields["user_type"] = role_map.get(role_raw, role_raw)

    # --- Delete travel expense: extract ID ---
    if task_type == TaskType.DELETE_TRAVEL_EXPENSE:
        # "Slett reiseregning 11142218" / "Delete travel expense 11142145"
        if "travel_expense_id" not in fields:
            m = re.search(
                r"(?:reiseregning|reiserekning|travel\s*expense|reisekostenabrechnung|note\s*de\s*frais)\s+(\d+)",
                text, re.I,
            )
            if m:
                fields["travel_expense_id"] = m.group(1)
            else:
                # Fallback: any standalone large number (travel expense IDs are typically 8+ digits)
                m = re.search(r"\b(\d{7,})\b", text)
                if m:
                    fields["travel_expense_id"] = m.group(1)

    return fields


def _extract_invoice_lines(text: str) -> list[dict]:
    """Extract invoice lines from natural language text.

    Patterns supported:
    - "N stk/pcs/units X til/at/à Y kr/NOK"
    - "N x X at Y"
    - "X, N stk, Y kr"
    """
    lines = []

    # Pattern: "N stk/pcs X til/at/for/à Y kr" (Norwegian/English)
    for m in re.finditer(
        r"(\d+)\s*(?:stk|pcs|units?|x)\s+(.+?)\s+(?:til|at|for|à|@)\s*(\d+[\d.,]*)\s*(?:kr|NOK|,-)?(?:\s+per\s+stk)?",
        text, re.I
    ):
        qty = int(m.group(1))
        desc = m.group(2).strip().rstrip(",.")
        price = float(m.group(3).replace(",", ".").replace(" ", ""))
        lines.append({"description": desc, "quantity": qty, "unit_price": price})

    # Pattern: "X - N stk à Y kr" or "X: N stk à Y kr"
    if not lines:
        for m in re.finditer(
            r"(.+?)[\s:,-]+(\d+)\s*(?:stk|pcs|units?)\s*(?:à|á|@|til|at|for)\s*(\d+[\d.,]*)\s*(?:kr|NOK)?",
            text, re.I
        ):
            desc = m.group(1).strip().rstrip(",.-:")
            qty = int(m.group(2))
            price = float(m.group(3).replace(",", ".").replace(" ", ""))
            if desc and len(desc) < 100:  # sanity check
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

    # Pattern: "N timer/hours X à/at Y kr" (time-based billing)
    if not lines:
        for m in re.finditer(
            r"(\d+)\s*(?:timer|hours?|t)\s+(.+?)\s+(?:à|á|@|til|at|for)\s*(\d+[\d.,]*)\s*(?:kr|NOK)?",
            text, re.I
        ):
            qty = int(m.group(1))
            desc = m.group(2).strip().rstrip(",.")
            price = float(m.group(3).replace(",", ".").replace(" ", ""))
            lines.append({"description": desc, "quantity": qty, "unit_price": price})

    return lines


async def _classify_rule_based(prompt: str, files: Optional[list[dict]] = None) -> TaskClassification:
    """Simple keyword-based classification with regex field extraction — no LLM required."""
    text = prompt.lower()
    for task_type, patterns in _KEYWORD_MAP:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                fields = _extract_fields_rule_based(task_type, prompt)
                return TaskClassification(
                    task_type=task_type,
                    confidence=0.6,
                    fields=fields,
                    raw_prompt=prompt,
                )

    # Last resort: single-word heuristic — NEVER return UNKNOWN if there's any signal
    _LAST_RESORT_WORDS = [
        (["faktura", "invoice", "factura", "rechnung", "facture", "fatura"], TaskType.CREATE_INVOICE),
        (["ansatt", "tilsett", "employee", "empleado", "mitarbeiter", "employé", "funcionário"], TaskType.CREATE_EMPLOYEE),
        (["kunde", "customer", "client", "cliente", "kunden"], TaskType.CREATE_CUSTOMER),
        (["avdeling", "department", "abteilung", "département", "departamento"], TaskType.CREATE_DEPARTMENT),
        (["prosjekt", "project", "projekt", "projet", "proyecto"], TaskType.CREATE_PROJECT),
        (["produkt", "product", "produit", "producto", "produto"], TaskType.CREATE_PRODUCT),
        (["timer", "hours", "timesheet", "timeliste", "stunden", "heures"], TaskType.LOG_HOURS),
        (["reiseregning", "reiserekning", "travel expense", "reisekosten", "frais de voyage"], TaskType.CREATE_TRAVEL_EXPENSE),
        (["kontaktperson", "contact", "contacto", "contato"], TaskType.CREATE_CONTACT),
        (["betaling", "payment", "innbetaling", "pago", "zahlung", "paiement"], TaskType.REGISTER_PAYMENT),
        (["kreditnota", "credit note", "gutschrift", "avoir"], TaskType.CREATE_CREDIT_NOTE),
        (["modul", "module"], TaskType.ENABLE_MODULE),
        (["bankavsteming", "reconcil", "avstem"], TaskType.BANK_RECONCILIATION),
        (["årsavslut", "årsoppgjør", "year-end"], TaskType.YEAR_END_CLOSING),
        (["korriger", "correct error", "feilrett"], TaskType.ERROR_CORRECTION),
    ]
    for words, fallback_type in _LAST_RESORT_WORDS:
        if any(w in text for w in words):
            fields = _extract_fields_rule_based(fallback_type, prompt)
            return TaskClassification(
                task_type=fallback_type,
                confidence=0.35,
                fields=fields,
                raw_prompt=prompt,
            )

    return TaskClassification(task_type=TaskType.UNKNOWN, confidence=0.0, fields={}, raw_prompt=prompt)


# ---------------------------------------------------------------------------
# Batch detection
# ---------------------------------------------------------------------------

_BATCH_NUM_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "to": 2, "tre": 3, "fire": 4, "fem": 5, "seks": 6, "sju": 7, "åtte": 8, "ni": 9, "ti": 10,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}

_BATCH_SINGULAR = {
    "avdelinger": "avdeling", "departments": "department",
    "ansatte": "ansatt", "employees": "employee",
    "kunder": "kunde", "customers": "customer",
    "produkter": "produkt", "products": "product",
    "prosjekter": "prosjekt", "projects": "project",
    "leverandører": "leverandør", "suppliers": "supplier",
    "kontakter": "kontakt", "contacts": "contact",
}


def _detect_batch(prompt: str) -> list[str] | None:
    """Detect batch operations like 'Create three departments: X, Y, Z'.

    Returns a list of individual sub-prompts, or None if not a batch.
    """
    # Pattern: "Create N <entities>: X, Y, Z" or "Create N <entities>: X, Y and Z"
    # Also: "Opprett N avdelinger: X, Y og Z"
    m = re.search(
        r"(?:opprett|create|lag|erstellen?|créer?|crear|criar|registrer)\s+"
        r"(\w+)\s+"
        r"(?:avdelinger?|departments?|ansatte|employees?|kunder?|customers?|produkter?|products?|prosjekter?|projects?|leverandører?|suppliers?|kontakter?|contacts?)"
        r"\s*:\s*(.+)",
        prompt, re.IGNORECASE
    )

    if not m:
        return None

    num_word = m.group(1).lower()
    expected_count = _BATCH_NUM_WORDS.get(num_word)
    if expected_count is None:
        try:
            expected_count = int(num_word)
        except ValueError:
            return None

    items_text = m.group(2).strip()

    # Split by comma and/or "og"/"and"/"und"/"et"/"y"/"e"
    # First replace " og ", " and ", etc. with comma
    items_text = re.sub(r'\s+(?:og|and|und|et|y|e)\s+', ', ', items_text, flags=re.IGNORECASE)
    items = [item.strip().rstrip('.,;') for item in items_text.split(',') if item.strip()]

    if not items:
        return None

    # Reconstruct individual prompts
    # Extract the entity type keyword from the original prompt
    entity_match = re.search(
        r"(avdelinger?|departments?|ansatte|employees?|kunder?|customers?|produkter?|products?|prosjekter?|projects?|leverandører?|suppliers?|kontakter?|contacts?)",
        prompt, re.IGNORECASE
    )
    entity_word = entity_match.group(1) if entity_match else "entity"
    singular = _BATCH_SINGULAR.get(entity_word.lower(), entity_word)

    # Detect the verb used
    verb_match = re.search(r"(opprett|create|lag|erstellen?|créer?|crear|criar|registrer)", prompt, re.IGNORECASE)
    verb = verb_match.group(1) if verb_match else "Opprett"

    sub_prompts = [f"{verb} {singular} {item}" for item in items]
    return sub_prompts


# ---------------------------------------------------------------------------
# Unified classifier dispatch
# ---------------------------------------------------------------------------

async def classify(prompt: str, files: Optional[list[dict]] = None) -> TaskClassification:
    """Route to the appropriate classifier based on LLM_MODE."""
    # --- Batch detection for non-Gemini modes ---
    # Gemini handles batches via its system prompt, but rule-based and Claude don't
    if LLM_MODE != "gemini":
        sub_prompts = _detect_batch(prompt)
        if sub_prompts:
            log("INFO", "Batch detected", count=len(sub_prompts), sub_prompts=sub_prompts)
            from classifier import _post_process_fields, _normalize_fields
            results = []
            for sp in sub_prompts:
                if LLM_MODE == "claude":
                    r = await _classify_with_claude(sp, files)
                else:
                    r = await _classify_rule_based(sp, files)
                r.fields = _post_process_fields(r.task_type, r.fields)
                r.fields = _normalize_fields(r.task_type, r.fields)
                results.append(r)
            return results

    if LLM_MODE == "gemini":
        from classifier import classify_task
        result = await classify_task(prompt, files)  # already applies _post_process_fields
    elif LLM_MODE == "claude":
        result = await _classify_with_claude(prompt, files)
    else:
        result = await _classify_rule_based(prompt, files)

    # Apply post-processing and normalization to Claude and rule-based paths
    if LLM_MODE != "gemini":
        from classifier import _post_process_fields, _normalize_fields
        result.fields = _post_process_fields(result.task_type, result.fields)
        result.fields = _normalize_fields(result.task_type, result.fields)

    # SAFETY NET: if still UNKNOWN after primary classifier, try rule-based as backup
    if result.task_type == TaskType.UNKNOWN and LLM_MODE != "none":
        log("WARNING", "Primary classifier returned UNKNOWN, trying rule-based fallback",
            prompt_preview=prompt[:150])
        fallback = await _classify_rule_based(prompt, files)
        if fallback.task_type != TaskType.UNKNOWN:
            from classifier import _post_process_fields, _normalize_fields
            fallback.fields = _post_process_fields(fallback.task_type, fallback.fields)
            fallback.fields = _normalize_fields(fallback.task_type, fallback.fields)
            log("INFO", "Rule-based fallback recovered", task_type=str(fallback.task_type))
            return fallback

    if result.task_type == TaskType.UNKNOWN:
        log("ERROR", "ALL classifiers returned UNKNOWN — this will score 0",
            prompt_preview=prompt[:200])

    return result


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Tripletex Agent", docs_url=None, redoc_url=None)

API_KEY = os.environ.get("API_KEY")


@app.get("/")
async def root():
    return {
        "service": "Tripletex AI Accounting Agent",
        "version": "1.0.0",
        "llm_mode": LLM_MODE,
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "llm_mode": LLM_MODE}


@app.post("/health")
async def health_post():
    return {"status": "ok"}


@app.post("/solve")
@app.post("/")
async def solve(request: Request):
    global _request_counter
    start = time.monotonic()

    # --- Optional Bearer auth ---
    if API_KEY:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer ") or auth_header[7:] != API_KEY:
            return JSONResponse({"status": "completed", "error": "unauthorized"}, status_code=401)

    # --- Parse request body ---
    try:
        body = await request.json()
    except Exception:
        log("ERROR", "Failed to parse request body")
        return JSONResponse({"status": "completed", "details": {"error": "invalid_request_body"}})

    prompt = body.get("prompt", "")
    files = body.get("files", [])
    creds = body.get("tripletex_credentials", {})

    base_url = creds.get("base_url", "") or body.get("tripletex_base_url", "")
    session_token = creds.get("session_token", "") or body.get("tripletex_session_token", "")

    log("INFO", "Received task", prompt_preview=prompt[:120], file_count=len(files))
    log("INFO", "Credential check",
        base_url=base_url,
        token_length=len(session_token) if session_token else 0,
        token_tail=session_token[-4:] if len(session_token) >= 4 else "***")

    if not base_url or not session_token:
        log("ERROR", "Missing Tripletex credentials", base_url_present=bool(base_url), token_present=bool(session_token))
        return JSONResponse({"status": "completed", "details": {"error": "missing_credentials"}})

    # --- Build client ---
    client = TripletexClient(base_url=base_url, session_token=session_token)

    result = None
    task_type = None
    try:
        # 1. Classify the task
        classification = await classify(prompt, files)

        from executor import execute_task

        # Handle batch classifications (list of tasks)
        if isinstance(classification, list):
            task_type = "BATCH"
            log("INFO", "Batch classification",
                count=len(classification),
                types=[str(c.task_type) for c in classification])
            results = []
            for cls in classification:
                try:
                    r = await execute_task(cls, client)
                    results.append(r)
                except Exception as e:
                    log("ERROR", "Batch item failed", task_type=str(cls.task_type), error=str(e))
                    results.append({"success": False, "error": str(e)})
            # Overall success if any succeeded
            any_success = any(r.get("success", False) for r in results if isinstance(r, dict))
            result = {"success": any_success, "batch_results": results, "batch_count": len(results)}
        else:
            task_type = str(classification.task_type)
            log("INFO", "Classified task",
                task_type=task_type,
                confidence=getattr(classification, "confidence", None),
                llm_mode=LLM_MODE,
                fields=classification.fields)

            # 2. Execute the task
            result = await execute_task(classification, client)
            log("INFO", "Task executed", result_keys=list(result.keys()) if isinstance(result, dict) else None)

    except ImportError as e:
        log("ERROR", "Module not available", error=str(e))
        result = {"success": False, "error": f"ImportError: {e}"}
    except Exception as e:
        log("ERROR", "Task execution failed", error=str(e), error_type=type(e).__name__)
        result = {"success": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        await client.close()

    # Log success/failure details
    if isinstance(result, dict) and result.get("success"):
        log("INFO", "Task succeeded", task_type=task_type, result=result)
    else:
        log("WARN", "Task did not succeed", task_type=task_type, result=result)

    # Request summary
    _request_counter += 1
    api_calls = getattr(client, 'api_call_count', 0)
    errors = getattr(client, 'error_count', 0)
    summary_lines = [
        f"╔══════════════════════════════════════════════════╗",
        f"║ Request #{_request_counter:>4}                                   ║",
        f"║ Task: {str(task_type)[:42]:<42} ║",
        f"║ API calls: {api_calls:<3}  Errors: {errors:<3}                    ║",
        f"║ Success: {'YES' if isinstance(result, dict) and result.get('success') else 'NO ':<3}                                       ║",
        f"╚══════════════════════════════════════════════════╝",
    ]
    for line in summary_lines:
        log("INFO", line)

    elapsed = time.monotonic() - start
    log("INFO", "Request complete", elapsed_seconds=round(elapsed, 2))

    # Always return {"status":"completed"} — the competition grader requires it.
    # Include details for our debugging.
    response = {"status": "completed"}
    if task_type:
        response["task_type"] = task_type
    if isinstance(result, dict):
        response["details"] = result
    return JSONResponse(response)
