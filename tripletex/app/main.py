"""Tripletex AI Accounting Agent — NM i AI 2026 competition endpoint.

Supports three LLM modes:
  1. Vertex AI Gemini (Cloud Run production) — when GEMINI_MODEL is set
  2. Anthropic Claude (local dev) — when ANTHROPIC_API_KEY is set
  3. Rule-based fallback (no LLM) — when neither is set
"""
from __future__ import annotations

import asyncio
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


_request_counter = 0


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


# ---------------------------------------------------------------------------
# Claude-based classifier (local dev)
# ---------------------------------------------------------------------------

_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(timeout=30.0)
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
- ONLY extract fields explicitly stated in the prompt. NEVER fabricate emails, phones, addresses, or websites not present in the input.
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
  slett=delete, oppdater=update, kontaktperson=contact, betaling=payment, kreditnota=credit_note,
  leverandør=supplier, leverandørfaktura/inngående faktura=supplier_invoice
- de: Erstellen=create, Abteilung=department, Abteilungsnummer=department_number, Mitarbeiter=employee,
  Buchhaltungsdimension=accounting_dimension, Beleg=voucher, Kostenstelle=cost_center,
  Lieferant/Lieferanten=supplier (NOT customer!), Registrieren=register
- fr: Créer=create, département=department, numéro=number, employé=employee, dimension=dimension,
  paie=payroll, salaire=salary, prime=bonus, fournisseur=supplier, enregistrez=register
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

Input: "Erstellen Sie eine benutzerdefinierte Buchhaltungsdimension 'Kostsenter' mit den Werten 'IT' und 'Innkjøp'. Buchen Sie dann einen Beleg auf Konto 7000 über 19450 NOK, verknüpft mit dem Dimensionswert 'IT'."
Output: {{"task_type":"create_dimension_voucher","confidence":0.97,"fields":{{"dimension_name":"Kostsenter","dimension_values":["IT","Innkjøp"],"account_number":"7000","amount":19450.0,"linked_dimension_value":"IT"}}}}

Input: "Registrer reiseregning for ansatt Ola Nordmann, tittel Kundebesøk Oslo"
Output: {{"task_type":"create_travel_expense","confidence":0.95,"fields":{{"employee_identifier":"Ola Nordmann","title":"Kundebesøk Oslo"}}}}

Input: "Registrieren Sie den Lieferanten Nordlicht GmbH mit der Organisationsnummer 922976457. E-Mail: faktura@nordlichtgmbh.no."
Output: {{"task_type":"create_supplier","confidence":0.97,"fields":{{"name":"Nordlicht GmbH","organization_number":"922976457","email":"faktura@nordlichtgmbh.no"}}}}

CRITICAL: Lieferant/leverandør/supplier = create_supplier (NOT create_customer). These are different entities in Tripletex.
CRITICAL: paie/lønn/payroll/Gehalt/salaire = run_payroll. Extract base_salary and bonus as separate numeric fields.
CRITICAL: "reverser betaling" / "payment returned/bounced by bank" / "Zahlung rückerstattet" → reverse_payment (NOT create_credit_note or error_correction). The goal is to reverse the payment voucher so the invoice is outstanding again.

Input: "Exécutez la paie de Jules Leroy (jules.leroy@example.org) pour ce mois. Le salaire de base est de 56950 NOK. Ajoutez une prime unique de 9350 NOK."
Output: {{"task_type":"run_payroll","confidence":0.97,"fields":{{"employee_identifier":"Jules Leroy","first_name":"Jules","last_name":"Leroy","email":"jules.leroy@example.org","base_salary":56950.0,"bonus":9350.0}}}}

Input: "Betalingen fra Tindra AS ble returnert av banken. Reverser betalingen slik at fakturaen igjen vises som utestående."
Output: {{"task_type":"reverse_payment","confidence":0.97,"fields":{{"customer_name":"Tindra AS"}}}}

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
        import asyncio
        response = await asyncio.to_thread(
            client.messages.create,
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
    (TaskType.ENABLE_MODULE, [r"\b(aktiver|enable|aktivieren|activer|activar|ativar|activate|attivare|habilitar)\w*\b.*\b(modul|module|módulo)\w*\b",
                               r"\w*(modul|module|módulo)\w*\b.*\b(aktiver|enable|aktivieren|activer|activar|ativar|activate|attivare|habilitar)\w*\b",
                               r"\b(aktiver|enable|aktivieren|activer|activar|ativar|activate|attivare|habilitar)\w*\b",
                               r"\w+(modul|module|módulo)(en|e|n)?\b",
                               r"\bslå\s+på\b.*\b(modul|module|módulo)\w*\b",
                               r"\bslaa\s+paa\b.*\b(modul|module|módulo)\w*\b",
                               r"\bsla\s+pa\b.*\b(modul|module|módulo)\w*\b",
                               r"\b(slå|slaa|sla)\s+(på|paa|pa)\b"]),
    # --- T3: Bank / Year-end / Error (before travel/employee to catch compound words) ---
    (TaskType.BANK_RECONCILIATION, [r"\bbankavstem\w*\b",
                                     r"\bbank\w*\b.*\bavstem\w*\b",
                                     r"\bavstem\w*\b.*\bbank\w*\b",
                                     r"\b(reconcil|abgleich|rapproch)\w*\b",
                                     r"\b(kontoabstimmung|kontenaustimmung)\w*\b",
                                     r"\bconciliaci[oó]n\s+bancaria\b",
                                     r"\bconcilia[çc][aã]o\s+banc[aá]ria\b",
                                     r"\briconciliazione\s+bancaria\b",
                                     r"\brapprochement\s+bancaire\b",
                                     r"\b(afstemming|bankafstemming|bankabstimmung)\w*\b",
                                     r"\bbankavstämning\w*\b",
                                     r"\breconciliaci[oó]n\s+bancaria\b",
                                     r"\breconcilia[çc][aã]o\s+banc[aá]ria\b",
                                     # French: "relevé bancaire" = bank statement
                                     r"\brelev[eé]\s+bancaire\b",
                                     # German: "Kontoauszug" = bank statement
                                     r"\bkontoauszug\w*\b",
                                     # Spanish: "extracto bancario" / "estado de cuenta"
                                     r"\bextracto\s+bancario\b",
                                     r"\bestado\s+de\s+cuenta\b.*\bbanco\b",
                                     # Portuguese: "extrato bancário"
                                     r"\bextrato\s+banc[aá]rio\b",
                                     # Norwegian: "kontoutskrift" = bank statement
                                     r"\bkontoutskrift\w*\b",
                                     # "solde initial" / "Anfangssaldo" / "saldo inicial" = initial balance
                                     r"\b(solde\s+initial|anfangssaldo|saldo\s+inicial)\b"]),
    # --- Payment returned / bounced / reversed → reverse_payment (before error correction) ---
    (TaskType.REVERSE_PAYMENT, [r"\b(devolvid|returned|bounced|rückerstattet|retourné|devuelto)\w*\b.*\b(pagamento|payment|betaling|zahlung|paiement|pago)\w*\b",
                                 r"\b(pagamento|payment|betaling|zahlung|paiement|pago)\w*\b.*\b(devolvid|returned|bounced|rückerstattet|retourné|devuelto)\w*\b",
                                 r"\b(reverser|reverse|undo|tilbakefør)\w*\b.*\b(betaling|payment|zahlung|paiement|pago)\w*\b",
                                 r"\b(returnert|returned|bounced)\w*\b.*\b(bank|betaling|payment)\w*\b"]),
    (TaskType.ERROR_CORRECTION, [r"\b(korriger|correct|fiks|fix)\w*\b.*\b(feil|error|bilag|voucher|postering)\b",
                                   r"\b(feil|error)\w*\b.*\b(korriger|correct|rett)\b",
                                   r"\b(reverser|reverse|tilbakefør)\w*\b.*\b(bilag|voucher|postering)\b",
                                   r"\b(korrigier|corrigir|correggere|corriger|corregir)\w*\b.*\b(buchung|écriture|scrittura|comprobante|lançamento|registrazione|postering|voucher|bilag|beleg)\b",
                                   r"\b(feilpostering|fehlbuchung|erreur\s+comptable|error\s+contable|erro\s+contábil)\w*\b",
                                   r"\b(korriger|rett|correct)\w*\b.*\b(feilpostering|fehlbuchung)\w*\b",
                                   r"\bcorrecci[oó]n\s+de\s+error\b",
                                   r"\bcorre[çc][aã]o\s+de\s+erro\b",
                                   r"\bfehlerkorrekt\w*\b",
                                   r"\bcorrection\s+d['\u2019]erreur\b",
                                   r"\b(feilretting|korreksjon|korrigering)\w*\b"]),
    (TaskType.YEAR_END_CLOSING, [r"\bårsavslut\w*\b", r"\barsavslut\w*\b", r"\baarsavslut\w*\b",
                                   r"\bårsoppgjør\w*\b", r"\barsoppgjor\w*\b", r"\baarsoppgjor\w*\b",
                                   r"\byear.?end\b", r"\bannual.?clos\w*\b",
                                   r"\bjahresabschluss\w*\b", r"\bclôture\b(?!\s*mensuel)", r"\bcierre\s+anual\b",
                                   r"\bencerramento\s+anual\b",
                                   r"\bchiusura\s+(annuale|d[ie]l?\s+esercizio)\b",
                                   r"\bfechamento\s+anual\b",
                                   r"\b(bokslut|årsbokslut|arsbokslut)\w*\b",
                                   r"\bclôture\s+annuelle\b",
                                   r"\b(fiscal\s+year|accounting\s+year)\b.*\b(clos|end|avslutt)\w*\b",
                                   r"\b(avslutt|close|lukk)\w*\b.*\b(år|year|ar|regnskapsår|regnskapsar)\w*\b"]),
    (TaskType.MONTH_END_CLOSING, [r"\bmånedsslutt\w*\b", r"\bmanedsslutt\w*\b",
                                   r"\bmånedsavslut\w*\b", r"\bmanedsavslut\w*\b",
                                   r"\bmonth.?end.?clos\w*\b", r"\bmonthly.?closing\b",
                                   r"\bmonatsabschluss\w*\b",
                                   r"\bclôture\s*mensuel\w*\b", r"\bcloture\s*mensuel\w*\b",
                                   r"\bcierre\s*mensual\b",
                                   r"\bfechamento\s*mensal\b",
                                   r"\bperiodisering\w*\b", r"\bperiodifikasjon\w*\b",
                                   r"\bperiodificación\w*\b",
                                   r"\bmonthly\s*accrual\w*\b", r"\bperiodenabgrenzung\w*\b",
                                   r"\bavskrivning\w*\b.*\bmåned\w*\b",
                                   r"\bmonthly\s*depreciation\b",
                                   r"\bmonatliche\w*\s*abschreibung\w*\b",
                                   r"\bamortissement\s*mensuel\w*\b",
                                   r"\bdepreciación\s*mensual\b",
                                   r"\b(avslutt|close|lukk)\w*\b.*\b(måned|month|monat|mois|mes)\w*\b"]),
    # --- Travel (after enable_module — "reiseregning" alone should match travel) ---
    # NOTE: "reise" without trailing \b so it matches "reiseregning" as substring
    (TaskType.DELETE_TRAVEL_EXPENSE, [r"\b(slett|delete|remove|fjern|löschen|eliminar|supprimer)\b.*\b(reise|travel|viaje|voyage|reisekostenabrechnung)",
                                       r"\b(slett|delete|remove|fjern)\b.*\b(?:reiseregning|reiserekning)\b"]),
    (TaskType.CREATE_TRAVEL_EXPENSE, [r"\breiseregning\b", r"\breiserekning\b",
                                       r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar)\b.*\b(reise|travel|viaje|voyage|reisekostenabrechnung)\b"]),
    # --- Employee (SET_EMPLOYEE_ROLES before UPDATE to catch "endre rolle" before "endre ansatt") ---
    (TaskType.DELETE_EMPLOYEE, [r"\b(slett|fjern|delete|remove|löschen|entfernen|eliminar|supprimer|excluir)\b.*\b(ansatt|tilsett|employee|empleado|mitarbeiter|employé|funcionário|empregado)\b"]),
    (TaskType.SET_EMPLOYEE_ROLES, [r"\b(rolle\w*|role\w*|access|tilgang|user.?type|brukertype)\b.*\b(ansatt|tilsett|employee|mitarbeiter|employé)\b",
                                    r"\b(ansatt|employee|mitarbeiter|employé)\b.*\b(rolle\w*|role\w*|access|tilgang|brukertype)\b",
                                    r"\b(sett|set|gi|give|assign|tildel|setzen)\b.*\b(ansatt|employee|mitarbeiter)\b.*\b(rolle\w*|role\w*|som|as|to|als)\b",
                                    r"\b(endre|change|sett)\b.*\b(rolle\w*|role\w*)\b",
                                    r"\b(eingeschränkt|restricted|begrenz)\w*\b.*\b(benutzer|user|bruker)\b",
                                    r"\b(administrator|admin|kontoadministrator)\b.*\b(ansatt|employee|mitarbeiter|tilsett)\b",
                                    r"\b(ansatt|employee|mitarbeiter|tilsett)\b.*\b(administrator|admin|kontoadministrator)\b"]),
    # --- Log Hours / Timesheet (MUST come before CREATE_EMPLOYEE — "Registrer timer for ansatt" matches both) ---
    (TaskType.LOG_HOURS, [r"\b(log|logg|registrer|register|føre?|enter|erfassen|enregistrer|registre)\b.*\b(timer|hours?|stunden|heures|horas|tid|time)\b",
                           r"\b(timer|hours?|timesheet|timefør\w*|tidregistrering|timeliste)\b.*\b(prosjekt|project|projekt|projet)\b",
                           r"\b(timesheet|timeliste|timefør\w*|tidregistrering|stundenzettel|feuille.de.temps)\b",
                           # Spanish: "Registre X horas para..." / "X horas para..."
                           r"\b\d+[\.,]?\d*\s+(horas|heures|stunden|timer)\b.*\b(para|pour|für|for)\b",
                           # "horas para <Name>" / "heures pour <Name>" / "Stunden für <Name>"
                           r"\b(horas|heures|stunden)\b.*\b(para|pour|für)\s+[A-ZÆØÅ\u00C0-\u024F]",
                           # verb forms: registre/enregistrez/erfassen Sie/anotar
                           r"\b(registre|enregistrez|anotar|registrar|erfassen)\w*\b.*\b(horas|heures|stunden|timer|hours)\b"]),
    (TaskType.UPDATE_EMPLOYEE, [r"\b(oppdater|endre|update|modify|ändra|aktualisieren|ändern|actualizar|modificar|modifier|atualizar)\b.*\b(ansatt|tilsett|employee|empleado|mitarbeiter|employé|empregado)\b",
                                 r"\b(legg\s+til|add)\b.*\b(e-post|epost|email|telefon|phone|tlf)\b.*\b(ansatt|tilsett|employee)\b",
                                 r"\b(ansatt|tilsett|employee)\b.*\b(legg\s+til|add)\b.*\b(e-post|epost|email|telefon|phone|tlf)\b"]),
    (TaskType.CREATE_EMPLOYEE, [r"\b(opprett?|lag|create|add|erstellen|créer|crear|criar|register|registrer|legg\s+til)\b.*\b(ansatt?e?|anstt|tilsett|employee|empleado|mitarbeiter|employé|funcionário|empregado)\b",
                                r"\bny\w?\b.*\b(ansatt?e?|anstt|tilsett|employee|empleado|mitarbeiter|employé)\b",
                                r"\b(ansatt?e?|tilsett|employee)\b.*\b(som\s+heter|named?|called)\b",
                                r"\b(ansatt?e?|tilsett|employee)\b.*\b(fornavn|first.?name|etternavn|last.?name)\b",
                                r"\boppre\w*\b.*\b(ansatt?|anstt)\b.*\b(e-?post|epost|email)\b"]),
    # --- Payroll (MUST come before employee patterns — "paie de X" should not match employee) ---
    (TaskType.RUN_PAYROLL, [
        r"\b(?:paie|payroll|lønn|lonn|gehalt|nómina|salaire|lønnskjøring|lønnsslipp|lonnsslipp|salary|lønnsutbetaling|lonnsutbetaling)\b",
        r"\b(?:lonnskjoring|loennskjoering)\b",
        r"\b(?:kjør|kjor|run|execute|exécutez|exécuter|ejecutar|processar|utfor|utfør)\b.*\b(?:lønn|lonn|payroll|paie|gehalt|nómina)\b",
        r"\bkjør\w*\s+lønn\w*\b",
    ]),
    # --- Dimension + Voucher (MUST come before invoice/voucher patterns — "Beleg" alone could trigger invoice) ---
    (TaskType.CREATE_DIMENSION_VOUCHER, [
        r"\b(?:dimensjon|dimension|buchhaltungsdimension|fri\s+dimensjon|custom\s+dimension|benutzerdefinierte\s+dimension)\b",
        r"\w*dimensjon\w*\b",
        r"\b(?:dimensi[oó][nm]|dimensão|dimensione)\w*\b",
        r"\b(?:kostsenter|kostenstelle|cost\s*center|kostnadssenter)\b",
        r"\b(?:dimensjonsverdier|dimensionswert|dimension\s*values?)\b",
        r"\b(?:regnskaps|accounting|buchhalter)\w*\s*dimensjon\w*\b",
        r"\bdimensjonsbilag\w*\b",
        r"\bprosjektdimensjon\w*\b",
        r"\bdimensi[oó]n\s+contable\b",
        r"\baccounting\s+dimension\b",
    ]),
    # --- Supplier Invoice (more specific — MUST come before supplier and regular invoice) ---
    # REGISTER_SUPPLIER_INVOICE = alias for CREATE_SUPPLIER_INVOICE (same executor)
    # NOTE: Keep patterns narrow — compound words like "leverandørfaktura" should match CREATE_SUPPLIER_INVOICE
    (TaskType.REGISTER_SUPPLIER_INVOICE, [
        r"\bleverandør(faktura|invoice)\w*\b",
        r"\bleverandor(faktura|invoice)\w*\b",
        r"leverandør.*faktura|faktura.*leverandør",
        r"leverandor.*faktura|faktura.*leverandor",
        r"\b(bokfør|bokfor|book)\w*\b.*\b(leverandør|leverandor|supplier|fournisseur|lieferant)\w*.*\bfaktura\w*\b",
        r"\b(registrer|bokfør|bokfor|book)\w*\b.*\b(inngående|incoming|mottatt)\w*\b.*\bfaktura\w*\b",
        r"(inngående|inngaaende|incoming|mottatt|motteke|received).*faktura",
        r"(registrer|register)\w*\s+faktura\w*\s+.*\b(leverandør|leverandor|supplier|fournisseur)\b",
        r"supplier.*invoice|Eingangsrechnung|facture.*fournisseur",
        r"registrar\s+factura\s+de\s+proveedor",
        r"registrar\s+fatura\s+de\s+fornecedor",
        r"registrere\s+leverandørfaktura",
        # German: "Rechnung vom/des Lieferanten" = invoice FROM supplier
        r"\brechnung\b.*\b(vom|des|von)\s+(lieferant|zulieferer)\w*\b",
        r"\b(lieferant|zulieferer)\w*\b.*\brechnung\b",
        # French: "facture du/de fournisseur"
        r"\bfacture\b.*\b(du|de)\s+fournisseur\b",
        # Spanish: "factura del/de proveedor"
        r"\bfactura\b.*\b(del|de)\s+proveedor\b",
        # Portuguese: "fatura do/de fornecedor"
        r"\bfatura\b.*\b(do|de)\s+fornecedor\b",
        # English: "invoice from supplier/vendor"
        r"\binvoice\b.*\bfrom\b.*\b(supplier|vendor)\b",
        # "vendor invoice" / "supplier invoice" (already above but ensure word boundary)
        r"\bvendor\s+invoice\b",
    ]),
    # --- Credit Note (MUST come before CREATE_SUPPLIER_INVOICE to avoid "invoice" matching supplier invoice) ---
    (TaskType.CREATE_CREDIT_NOTE, [r"\b(kreditnota|credit.?note|gutschrift|avoir|nota de crédito)\b",
                                    r"\bkreditere?\b.*\b(faktura|invoice)\b",
                                    r"\bkrediter\w*\s+faktura\b"]),
    (TaskType.CREATE_SUPPLIER_INVOICE, [
        r"leverandør.*faktura|faktura.*leverandør",
        r"leverandorfaktura|leverandørfaktura",
        r"leverandor.*faktura|faktura.*leverandor",
        r"(inngående|inngaaende|incoming|mottatt|motteke|received).*(faktura|invoice)",
        r"(registrer|register)\w*\s+faktura\w*\s+.*\b(leverandør|leverandor|supplier|fournisseur)\b",
        r"supplier.*invoice|Eingangsrechnung|facture.*fournisseur",
    ]),
    # --- Supplier (register supplier entity — after supplier invoice, before customer) ---
    (TaskType.CREATE_SUPPLIER, [
        r"\b(?:registrer|opprett|create|register|add|erstellen|registrieren|créer|crear|criar|enregistre)\w*\b.*\b(?:leverandør|supplier|fournisseur|lieferant|proveedor|fornecedor)\w*\b",
        r"\b(?:leverandør|supplier|fournisseur|lieferant|proveedor|fornecedor)\w*\b.*\b(?:registrer|opprett|create|register|add|erstellen|registrieren|enregistre)\w*\b",
        r"\b(?:ny|new|neu|nouveau|nuevo|novo)\s+(?:leverandør|supplier|fournisseur|lieferant|proveedor|fornecedor)\b",
    ]),
    (TaskType.INVOICE_WITH_PAYMENT, [r"\b(faktura|invoice|factura|rechnung|facture)\b.*\b(betaling|payment|betalt|paid|pago|zahlung|paiement)\b",
                                     r"\b(facture|faktura|invoice|rechnung)\s+impayée?\b",
                                     r"\b(unbezahlte|impayée?|unpaid)\b.*\b(rechnung|facture|invoice|faktura)\b",
                                     r"\bclient\w*\b.*\bfacture\b.*\bimpayée?\b"]),
    (TaskType.REGISTER_PAYMENT, [r"\b(registrer|register|registreer)\w*\b.*\b(betaling|innbetaling|payment|pago|zahlung|paiement)\b",
                                  r"\b(betaling|payment|pago|zahlung|paiement)\b.*\b(faktura|invoice|factuur|factura|rechnung|facture)\b",
                                  r"\bbetal\w*\s+faktura\b",
                                  r"\bpay\w*\s+invoice\b",
                                  r"\binnbetaling\b.*\b(faktura|invoice)\b"]),
    (TaskType.INVOICE_EXISTING_CUSTOMER, [r"\b(faktura|invoice|factura|rechnung)\b.*\b(kund(?:e|en)|customer|client|cliente)\b",
                                          r"\b(faktura|invoice)\b\s+(?:til|to|for|an)\s+[A-ZÆØÅ]",
                                          r"\bfaktur\w*\b.*\b(kund(?:e|en)|customer|client|cliente)\b"]),
    (TaskType.CREATE_INVOICE, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar)\b.*\b(faktura|invoice|factura|rechnung|facture|fatura)\b",
                                r"\b(sende?|send)\b.*\b(regning|faktura|invoice)\b",
                                r"\b(faktura|invoice|factura|rechnung|facture|fatura)\b"]),
    # --- Contact (use "kontaktperson" not bare "kontakt" to avoid matching email addresses like kontakt@...) ---
    (TaskType.UPDATE_CONTACT, [r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\b(kontaktperson|kontakt(?!@)|contact(?!@)|contacto|contato)\b",
                                r"\b(kontaktperson|kontakt)\b.*\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b"]),
    (TaskType.CREATE_CONTACT, [r"\bkontaktperson\b", r"\b(opprett|create|add|erstellen|créer|crear|criar)\b.*\b(contactperson|kontakt(?!@)|contact(?!@)|contacto|contato)\b"]),
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
    (TaskType.FIND_CUSTOMER, [r"\b(finn|find|search|søk|suchen|buscar|chercher|procurar|encontrar)\b.*\b(kund(?:e|en)|customer|client|cliente)\b"]),
    (TaskType.CREATE_CUSTOMER, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar|registrer|register|legg\s+til|add|set\s+up)\b.*\b(kund(?:e|en)|customer|client|cliente)\b",
                                r"\bny\w?\b.*\b(kund(?:e|en)|customer|client|cliente)\b",
                                r"\b(kund(?:e|en)|customer|client|cliente)\b.*\b(opprett|create|lag)\b"]),
    # --- Product / Department ---
    (TaskType.DELETE_PRODUCT, [r"\b(slett|fjern|delete|remove|löschen|entfernen|eliminar|supprimer|excluir)\b.*\b(produkt\w*|product\w*|producto\w*|produit\w*|produto\w*)\b"]),
    (TaskType.UPDATE_PRODUCT, [r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\b(produkt\w*|product\w*|producto\w*|produit\w*|produto\w*)\b"]),
    (TaskType.CREATE_PRODUCT, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar|registrer|register|legg\s+til|add)\b.*\b(produkt\w*|product\w*|producto\w*|produit\w*|produto\w*)\b",
                                r"\bny\w?\b.*\b(produkt\w*|product\w*|producto\w*|produit\w*|produto\w*)\b"]),
    # --- Supplier management (after supplier invoice) ---
    (TaskType.DELETE_SUPPLIER, [r"\b(slett|fjern|delete|remove|löschen|entfernen|eliminar|supprimer|excluir)\b.*\b(leverandør\w*|supplier\w*|fournisseur\w*|lieferant\w*|proveedor\w*|fornecedor\w*)\b"]),
    (TaskType.FIND_SUPPLIER, [r"\b(finn|find|search|søk|suchen|buscar|chercher|procurar|encontrar)\b.*\b(leverandør\w*|supplier\w*|fournisseur\w*|lieferant\w*|proveedor\w*|fornecedor\w*)\b"]),
    (TaskType.UPDATE_SUPPLIER, [r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\b(leverandør\w*|supplier\w*|fournisseur\w*|lieferant\w*|proveedor\w*|fornecedor\w*)\b"]),
    # --- Department ---
    (TaskType.DELETE_DEPARTMENT, [r"\b(slett|fjern|delete|remove|löschen|entfernen|eliminar|supprimer|excluir)\b.*\b(avdeling\w*|department\w*|departamento\w*|abteilung\w*|département\w*)\b"]),
    (TaskType.UPDATE_DEPARTMENT, [r"\b(oppdater|endre|update|modify|aktualisieren|ändern|actualizar|modifier|atualizar)\b.*\b(avdeling\w*|department\w*|departamento\w*|abteilung\w*|département\w*)\b"]),
    (TaskType.CREATE_DEPARTMENT, [r"\b(opprett\w*|create|lag\w?|erstellen|créer|crear|criar|registrer|register|legg\s+til|add)\b.*\b(avdeling\w*|department\w*|departamento\w*|abteilung\w*|département\w*)\b",
                                   r"\bny\w?\b.*\b(avdeling\w*|department\w*|departamento\w*|abteilung\w*|département\w*)\b",
                                   r"\b(avdeling\w*|department\w*|departamento\w*|abteilung\w*|département\w*)\b.*\b(opprett|create|lag)\b"]),
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
    if task_type in (TaskType.CREATE_EMPLOYEE, TaskType.UPDATE_EMPLOYEE, TaskType.DELETE_EMPLOYEE,
                     TaskType.SET_EMPLOYEE_ROLES):
        # Pattern 1: "ansatt/employee [named] X Y" (two-name)
        # re.I needed: German capitalizes nouns ("Mitarbeiter" vs "mitarbeiter")
        m = re.search(
            r"(?:ansatt|tilsett|employee|empleado|mitarbeiter|employé|funcionário)\s+"
            r"(?:med\s+navn\s+|named?\s+|called\s+|namens\s+|appelée?\s+|chamad[oa]\s+|kalt\s+)?"
            r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)",
            text, re.I,
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

        # Pattern 3: Single-name fallback — "ansatt/employee X" (only one name given)
        # re.I needed: German capitalizes nouns ("Mitarbeiter" vs "mitarbeiter")
        if "first_name" not in fields and "employee_identifier" not in fields:
            m = re.search(
                r"(?:ansatt|tilsett|employee|empleado|mitarbeiter|employé|funcionário)\s+"
                r"(?:med\s+navn\s+|named?\s+|called\s+|namens\s+|kalt\s+)?"
                r"([A-ZÆØÅ\u00C0-\u024F]\S+)",
                text, re.I,
            )
            if m:
                fields["employee_identifier"] = m.group(1).rstrip(",.")

    # --- Supplier name extraction (for find/delete/update supplier) ---
    _SUPPLIER_TASK_TYPES = (TaskType.FIND_SUPPLIER, TaskType.DELETE_SUPPLIER,
                            TaskType.UPDATE_SUPPLIER, TaskType.CREATE_SUPPLIER)
    if "name" not in fields and task_type in _SUPPLIER_TASK_TYPES:
        m = re.search(
            r"(?:leverandør(?:en)?|supplier|fournisseur|lieferant(?:en)?|proveedor|fornecedor|"
            r"fornitore|dostawc[aę])\s+"
            r"(\S+(?:\s+(?:AS|ASA|SA|GmbH|Ltd|Inc|Corp|AB|ApS|AG|SRL|SARL|Lda|SL))?)"
            r"(?:\s*[,(.]|\s+(?:med|with|org|på|for|til|mit|avec|con|por|aus|du|from|von|de|par|"
            r"fra|im|nel|no|em|i)\s|$)",
            text, re.I,
        )
        if m:
            fields["name"] = m.group(1).strip().rstrip(",.")

    # --- Department name extraction (for delete/update department) ---
    if "name" not in fields and task_type in (TaskType.DELETE_DEPARTMENT, TaskType.UPDATE_DEPARTMENT):
        m = re.search(
            r"(?:avdeling(?:a|en)?|department|département|departamento|abteilung|"
            r"dipartimento|departement)\s+"
            r"(\S+(?:\s+(?:og|and|och|und|et|e|y)\s+\S+)*)"
            r"(?:\s*[,(.]|\s+(?:med|with|org|på|for|til|mit|avec|con|por|aus|du|from|von|de|par|"
            r"fra|im|nel|no|em|i)\s|$)",
            text, re.I,
        )
        if m:
            fields["name"] = m.group(1).strip().rstrip(",.")
            if task_type == TaskType.UPDATE_DEPARTMENT:
                fields["department_name"] = fields["name"]

    # Entity-keyword + name (for departments, products, projects without "med navn"/"named")
    # "avdeling HR", "department Finance", "Abteilung Vertrieb", "produkt Widget"
    _NAME_ENTITY_TYPES = (TaskType.CREATE_DEPARTMENT, TaskType.CREATE_PRODUCT,
                          TaskType.CREATE_PROJECT, TaskType.CREATE_CUSTOMER,
                          TaskType.PROJECT_WITH_CUSTOMER, TaskType.FIND_CUSTOMER,
                          TaskType.UPDATE_CUSTOMER, TaskType.UPDATE_PROJECT,
                          TaskType.UPDATE_PRODUCT, TaskType.DELETE_PRODUCT,
                          TaskType.DELETE_PROJECT, TaskType.DELETE_DEPARTMENT,
                          TaskType.UPDATE_DEPARTMENT)
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
        # Fallback: unquoted name (capture word(s) after entity keyword, stop at known delimiters)
        if "name" not in fields:
            m = re.search(
                r"(?:avdeling\w*|department\w*|département\w*|departamento\w*|abteilung\w*|"
                r"produkt\w*|product\w*|produit\w*|producto\w*|produto\w*|"
                r"prosjekt\w*|project\w*|projet\w*|proyecto\w*|projeto\w*|"
                r"kund(?:e|en)\w*|customer\w*|client\w*|cliente\w*)\s+"
                r"(?:med\s+(?:namn\s+|navn\s+)?|named?\s+|called\s+|kalt\s+|appelée?\s+|nommée?\s+|"
                r"namens\s+|genannt\s+|chamad[oa]\s+|llamad[oa]\s+)?"
                r"([A-Za-zÆØÅæøå\u00C0-\u024F][\w&-]+"
                r"(?:\s+(?!(?:og|and|avec|mit|con|com|med|with|und|et|til|at|for|zu|à|"
                r"nummer|number|numéro|número|pris|price|prix|Preis|precio|preço|"
                r"ny|new|neu|nouveau|nuevo|novo|start|fra|from|von|de|du|par|por|aus)\b)"
                r"[A-Za-zÆØÅæøå\u00C0-\u024F&][\w&-]+)*)"
                r"(?:\s*[,.]|\s+(?:og|and|avec|mit|con|com|med|with|und|et|til|at|for|zu|à|"
                r"nummer|number|numéro|número|avdelingsnummer|abteilungsnummer|"
                r"department.?number|e-post|email|telefon|phone|pris|price|prix|Preis|precio|preço|"
                r"ny|new|neu|nouveau|nuevo|novo|start|fra|from|von|de|du|par|por|aus)\b|$)",
                text, re.I,
            )
            if m:
                fields["name"] = m.group(1).strip().rstrip(".,")

    # --- Email ---
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    if m:
        fields["email"] = m.group(0)

    # --- Phone (multilingual) ---
    m = re.search(r"(?:telefon(?:nummer)?|phone(?:\s*number)?|tlf|mobil|téléphone|teléfono|Telefon|"
                  r"celular|cellulare|numer\s*telefonu|Handynummer|numéro\s*(?:de\s*)?téléphone|"
                  r"número\s*(?:de\s*)?teléfono)\s*:?\s*([\d\s\+\-()]+)", text, re.I)
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
    m = re.search(
        r"(?:org\.?(?:anisasjonsnummer|anisationsnummer|\.?\s*nr\.?)?|organization\s*number|"
        r"número\s*(?:de\s*)?organización|numéro\s*(?:d['\u2019]\s*)?organisation|"
        r"Organisationsnummer|organisasjonsnummer|organisationsnummer|"
        r"numero\s*(?:di\s*)?organizzazione|número\s*(?:de\s*)?organiza[çc][ãa]o)"
        r"\s*:?\s*([\d\-\s]{9,})",
        text, re.I,
    )
    if m:
        fields["organization_number"] = m.group(1).replace("-", "").replace(" ", "").strip()

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
        elif any(w in text_lower for w in ["begrenset", "restricted", "limited", "eingeschränkt"]):
            fields["user_type"] = "NO_ACCESS"
        elif "ingen tilgang" in text_lower or "no access" in text_lower or "ohne registrierungszugang" in text_lower:
            fields["user_type"] = "NO_ACCESS"
        elif "standard" in text_lower:
            fields["user_type"] = "STANDARD"

    # --- Address ---
    if task_type in (TaskType.CREATE_CUSTOMER, TaskType.CREATE_EMPLOYEE, TaskType.UPDATE_CUSTOMER,
                     TaskType.CREATE_SUPPLIER, TaskType.UPDATE_SUPPLIER, TaskType.CREATE_CONTACT):
        # "adresse Storgata 5, 3015 Drammen" / "address 123 Main St, 0001 Oslo"
        m = re.search(r"(?:adresse|address|Adresse|dirección|endereço|adresse|indirizzo|Anschrift)\s*:?\s*(.+?)(?:\s*[.,]\s*(\d{4,5})\s+(\S+(?:\s+\S+)?))?(?:\s*[.,]|$)", text, re.I)
        if m:
            fields["address_line1"] = m.group(1).strip().rstrip(".,")
            if m.group(2):
                fields["postal_code"] = m.group(2)
            if m.group(3):
                fields["city"] = m.group(3).strip().rstrip(".,")

    # --- Contact-specific: customer name + contact name extraction ---
    if task_type == TaskType.CREATE_CONTACT:
        # "kontaktperson X Y for/hos/bei kunde/customer Z"
        m = re.search(
            r"(?:kontaktperson|kontakt|contact|Ansprechpartner|contacto|contato)\s+"
            r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)"
            r"(?:\s+(?:for|hos|bei|für|pour|para|per|at|chez)\s+(?:kund(?:e|en)|customer|client|cliente|Kunde)?\s*(.+?))?(?:\s*[.,]|$)",
            text, re.I,
        )
        if m:
            if "first_name" not in fields:
                fields["first_name"] = m.group(1).rstrip(",.")
            if "last_name" not in fields:
                fields["last_name"] = m.group(2).rstrip(",.")
            if m.group(3) and "customer_name" not in fields:
                fields["customer_name"] = m.group(3).strip().rstrip(",.")
        # Fallback: "legg til X Y som kontakt" / "add X Y as contact"
        if "first_name" not in fields:
            m = re.search(
                r"(?:legg\s+til|add|créer|crear|erstelle|cria[r]?)\s+"
                r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)"
                r"\s+(?:som\s+)?(?:kontakt|contact|Kontakt|contacto|contato)",
                text, re.I,
            )
            if m:
                fields["first_name"] = m.group(1).rstrip(",.")
                fields["last_name"] = m.group(2).rstrip(",.")
        # Customer name: "for/hos kunde X" / "for customer X"
        if "customer_name" not in fields:
            m = re.search(
                r"(?:for|hos|bei|für|pour|para|per|at|chez)\s+"
                r"(?:kund(?:e|en)|customer|client|cliente|Kunde|Client)?\s*"
                r"([A-ZÆØÅ\u00C0-\u024F][\w\s&-]+?)(?:\s*[.,]|\s+(?:med|with|og|and|e-post|email|telefon|phone)\b|$)",
                text, re.I,
            )
            if m:
                fields["customer_name"] = m.group(1).strip().rstrip(",.")
        # Title/role: "med rolle X" / "title X" / "stilling X"
        m = re.search(
            r"(?:rolle|role|stilling|title|tittel|position|Titel|título|titre|cargo)\s*:?\s*"
            r"(.+?)(?:\s*[.,]|\s+(?:for|hos|bei|med|with|og|and)\b|$)",
            text, re.I,
        )
        if m:
            fields["title"] = m.group(1).strip().rstrip(",.")

    # --- Website ---
    m = re.search(r"(?:nettside|website|webside|hjemmeside|Webseite|sitio\s*web|site\s*web|sito\s*web)\s*:?\s*(https?://\S+|www\.\S+|\S+\.\w{2,4})", text, re.I)
    if m:
        fields["website"] = m.group(1).strip()

    # --- Description ---
    m = re.search(r"(?:beskrivelse|description|Beschreibung|descripción|descrição|descrizione)\s*:?\s*(.+?)(?:\s*[.,]|$)", text, re.I)
    if m and "description" not in fields:
        fields["description"] = m.group(1).strip().rstrip(",.")

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
        # Extract profit/loss amount
        m = re.search(
            r"(?:resultat|profit|loss|gewinn|verlust|bénéfice|perte|ganancia|pérdida|lucro|prejuízo|overskudd|underskudd)\s*:?\s*[-−]?\s*(\d[\d\s.,]*)\s*(?:kr|NOK|EUR|USD)?",
            text, re.I,
        )
        if m:
            amt_str = m.group(1).replace(",", ".").replace(" ", "")
            try:
                fields["profit_loss"] = float(amt_str)
            except ValueError:
                pass

    if task_type == TaskType.MONTH_END_CLOSING:
        # Extract year
        m = re.search(r"\b(20\d{2})\b", text)
        if m:
            fields["year"] = m.group(1)
        # Extract month — Norwegian/English/German/French/Spanish month names or numbers
        month_map = {
            "januar": "01", "february": "02", "mars": "03", "april": "04",
            "mai": "05", "juni": "06", "juli": "07", "august": "08",
            "september": "09", "oktober": "10", "november": "11", "desember": "12",
            "january": "01", "february": "02", "march": "03", "may": "05",
            "june": "06", "july": "07", "october": "10", "december": "12",
            "januar": "01", "februar": "02", "märz": "03", "marz": "03",
            "juin": "06", "juillet": "07", "août": "08", "aout": "08",
            "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12",
            "enero": "01", "febrero": "02", "marzo": "03", "mayo": "05",
            "junio": "06", "julio": "07", "agosto": "08", "septiembre": "09",
            "octubre": "10", "noviembre": "11", "diciembre": "12",
            "janeiro": "01", "fevereiro": "02", "março": "03", "maio": "05",
            "junho": "06", "julho": "07", "setembro": "09",
            "outubro": "10", "dezembro": "12",
        }
        for name, num in month_map.items():
            if re.search(rf"\b{name}\b", text, re.I):
                fields["month"] = num
                break
        if "month" not in fields:
            m = re.search(r"\b(0?[1-9]|1[0-2])\s*[/.-]\s*(20\d{2})\b", text)
            if m:
                fields["month"] = f"{int(m.group(1)):02d}"
                fields["year"] = m.group(2)
        # Extract account number (multilingual: konto, account, cuenta, compte, Konto)
        m = re.search(r"\b(?:konto|account|cuenta|compte|Konto)\w*\s+(\d{4})\b", text, re.I)
        if m:
            fields["account_number"] = m.group(1)
            fields["accrual_from_account"] = m.group(1)
        # Extract amounts — try to get accrual and depreciation separately
        amounts = re.findall(r"(\d[\d\s.,]*\d)\s*(?:kr|NOK|EUR|USD)", text, re.I)
        if amounts:
            fields["amount"] = float(amounts[0].replace(",", ".").replace(" ", ""))
            if len(amounts) >= 2:
                fields["accrual_amount"] = float(amounts[0].replace(",", ".").replace(" ", ""))
        # Extract annual depreciation (e.g. "depreciación anual de 10000 NOK")
        dep_ann = re.search(r"(?:avskrivning|depreci\w*|abschreibung)\w*\s*(?:anual|annual|årlig|arlig|annuel\w*|jährlich\w*|jahrlich\w*)\D{0,20}(\d[\d\s.,]*\d)", text, re.I)
        if dep_ann:
            fields["annual_depreciation"] = float(dep_ann.group(1).replace(",", ".").replace(" ", ""))
        # Extract acquisition cost (e.g. "costo de adquisición 61000 NOK")
        cost_match = re.search(r"(?:kostpris|anskaffelse|innkjøpspris|costo\s+de\s+adquisici[oó]n|acquisition\s+cost|anschaffungskosten)\D{0,20}(\d[\d\s.,]*\d)", text, re.I)
        if cost_match:
            fields["depreciation_cost"] = float(cost_match.group(1).replace(",", ".").replace(" ", ""))

    if task_type == TaskType.ENABLE_MODULE:
        m = re.search(r"(?:modul|module|funksjon|feature)\s+(.+?)(?:\s*[,.]|$)", text, re.I)
        if m:
            fields["module_name"] = m.group(1).strip()

    if task_type == TaskType.CREATE_DIMENSION_VOUCHER:
        # Extract quoted values for dimension_name and dimension_values
        quoted = re.findall(r"""['"\u2018\u2019\u201C\u201D]([^'"\u2018\u2019\u201C\u201D]+)['"\u2018\u2019\u201C\u201D]""", text)
        if quoted:
            fields["dimension_name"] = quoted[0]
            if len(quoted) > 1:
                # linked_dimension_value: look for association keyword + quoted value
                link_match = re.search(
                    r"(?:verknüpft|linked|knyttet|lié|vinculado|associé)\s+(?:mit|with|til|med|à|a|con)?\s*(?:dem\s+)?(?:Dimensionswert|dimension\s*value?|dimensjonsverdien?)?\s*['\u2018\u2019\u201C\u201D\"']([^'\u2018\u2019\u201C\u201D\"']+)['\u2018\u2019\u201C\u201D\"']",
                    text, re.I,
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
                if not fields.get("linked_dimension_value") and len(dim_values) == 1:
                    fields["linked_dimension_value"] = dim_values[0]
        # Account number: "Konto 7000" / "account 7000"
        m = re.search(r"(?:konto|account|Konto|compte|cuenta)\s*:?\s*(\d{4})", text, re.I)
        if m:
            fields["account_number"] = m.group(1)
        # Amount: "19450 NOK" / "über 19450"
        m = re.search(r"(?:über|over|for|på|av|of|om|por|pour)?\s*(\d+[\d.,]*)\s*(?:kr|NOK)", text, re.I)
        if m:
            amt_str = m.group(1).replace(",", ".").replace(" ", "")
            try:
                fields["amount"] = float(amt_str)
            except ValueError:
                pass

    if task_type == TaskType.BANK_RECONCILIATION:
        # Extract account number: "konto 1920" / "account 1920" / "cuenta 1920"
        m = re.search(r"(?:konto|account|Konto|compte|cuenta|conta)\s*:?\s*(\d+)", text, re.I)
        if m:
            fields["account_number"] = m.group(1)
        # Extract period: "mars 2026" / "March 2026" / "2026-03"
        m = re.search(r"(?:for\s+)?(?:januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember|"
                      r"january|february|march|april|may|june|july|august|september|october|november|december|"
                      r"enero|febrero|marzo|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|"
                      r"janeiro|fevereiro|março|maio|junho|julho|setembro|outubro|dezembro|"
                      r"januar|februar|märz|marz|juin|juillet|août|aout|septembre|octobre|novembre|décembre)\s+(\d{4})", text, re.I)
        if m:
            fields["period"] = m.group(0).strip()
        # Extract date range: "fra 2026-03-01 til 2026-03-31" / "from ... to ..."
        m = re.search(r"(?:fra|from|von|de|du|desde)\s+(\d{4}-\d{2}-\d{2})\s+(?:til|to|bis|à|hasta|até)\s+(\d{4}-\d{2}-\d{2})", text, re.I)
        if m:
            fields["from_date"] = m.group(1)
            fields["to_date"] = m.group(2)
        # Extract single date: "dato 2026-03-15" / "date 2026-03-15"
        if "from_date" not in fields:
            m = re.search(r"(?:dato|date|Datum|fecha|data)\s*:?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
            if m:
                fields["date"] = m.group(1)

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
            r"(?:avdeling\w*|department\w*|département\w*|departamento\w*|abteilung\w*)\s+"
            r"(.+?)(?:\s*[,.]|\s+(?:med|with|mit|og|and|avec|con|til|to)\s|$)",
            text, re.I,
        )
        if m:
            fields["department_identifier"] = m.group(1).strip().rstrip(",.")
            fields["department_name"] = fields["department_identifier"]
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
        # re.I needed: German capitalizes nouns ("Mitarbeiter" vs "mitarbeiter")
        if "first_name" not in fields:
            m = re.search(
                r"(?:ansatt|tilsett|employee|mitarbeiter|employé|empleado)\s+"
                r"(?:role\s+)?(?:for\s+)?"
                r"([A-ZÆØÅ\u00C0-\u024F0-9]\S+)\s+([A-ZÆØÅ\u00C0-\u024F0-9]\S+)",
                text, re.I,
            )
            if m:
                fields["first_name"] = m.group(1).rstrip(",.")
                fields["last_name"] = m.group(2).rstrip(",.")
                fields["employee_identifier"] = f"{fields['first_name']} {fields['last_name']}"
        # Extract user type: "som administrator" / "as STANDARD" / "rollen prosjektleder" / "als eingeschränkten Benutzer"
        m = re.search(
            r"(?:som|as|als|to|til|rollen?)\s+(administrator|admin|standard|extended|no.?access|begrenset|limited|"
            r"eingeschränkt\w*|restricted|"
            r"prosjektleder|project.?manager|kontoadministrator|account.?administrator|"
            r"lønnsadministrator|payroll.?administrator|regnskapsfører|accountant)",
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
                "RESTRICTED": "NO_ACCESS",
                "PROSJEKTLEDER": "EXTENDED",
                "PROJECT_MANAGER": "EXTENDED",
                "KONTOADMINISTRATOR": "EXTENDED",
                "ACCOUNT_ADMINISTRATOR": "EXTENDED",
                "LØNNSADMINISTRATOR": "EXTENDED",
                "PAYROLL_ADMINISTRATOR": "EXTENDED",
                "REGNSKAPSFØRER": "EXTENDED",
                "ACCOUNTANT": "EXTENDED",
            }
            # Handle German inflected forms: eingeschränkten/eingeschränkter → eingeschränkt
            if role_raw.startswith("EINGESCHRÄNKT"):
                role_raw = "EINGESCHRÄNKT"
            mapped = role_map.get(role_raw)
            if not mapped:
                # Check executor's _UT_MAP as fallback
                mapped = {"EINGESCHRÄNKT": "NO_ACCESS", "EINGESCHRAENKT": "NO_ACCESS"}.get(role_raw, "STANDARD")
            fields["user_type"] = mapped

    # --- Payroll: extract employee, salary, bonus ---
    if task_type == TaskType.RUN_PAYROLL:
        # Employee name: "de Jules Leroy" / "for ansatt Kari Hansen" / "für Mitarbeiter X Y"
        # re.I needed: German capitalizes nouns ("Mitarbeiter")
        m = re.search(
            r"(?:de|for|für|pour|para|av|of)\s+(?:ansatt\s+|employee\s+|mitarbeiter\s+|employé\s+)?"
            r"([A-ZÆØÅ\u00C0-\u024F]\S+)\s+([A-ZÆØÅ\u00C0-\u024F]\S+)",
            text, re.I,
        )
        if m:
            fields["first_name"] = m.group(1).rstrip(",.")
            fields["last_name"] = m.group(2).rstrip(",.")
            fields["employee_identifier"] = f"{fields['first_name']} {fields['last_name']}"
        # Base salary
        m = re.search(
            r"(?:salaire\s+de\s+base|grunnlønn|grundgehalt|base\s+salary|sueldo\s+base|basislønn)\s+(?:est\s+de\s+|er\s+|ist\s+)?(\d[\d\s.,]*)\s*(?:kr|NOK)?",
            text, re.I,
        )
        if m:
            fields["base_salary"] = float(m.group(1).replace(",", ".").replace(" ", ""))
        else:
            # Fallback: first amount
            m = re.search(r"(\d+[\d.,]*)\s*(?:kr|NOK)", text, re.I)
            if m:
                fields["base_salary"] = float(m.group(1).replace(",", ".").replace(" ", ""))
        # Bonus
        m = re.search(
            r"(?:prime|bonus|tillegg|Prämie|Zuschlag|bonificación|bônus|gratification)\s+(?:unique\s+)?(?:de\s+|på\s+|von\s+|of\s+)?(\d[\d\s.,]*)\s*(?:kr|NOK)?",
            text, re.I,
        )
        if m:
            fields["bonus"] = float(m.group(1).replace(",", ".").replace(" ", ""))

    # --- Supplier: extract name, org number, email ---
    if task_type == TaskType.CREATE_SUPPLIER:
        m = re.search(
            r"(?:leverandør(?:en)?|supplier|fournisseur|lieferant(?:en)?|proveedor|fornecedor)\s+"
            r"([A-ZÆØÅ\u00C0-\u024F][\w\s]*?(?:AS|ASA|SA|GmbH|Ltd|Inc|Corp|AB|ApS|AG|SRL|SARL|Lda|SL)?)\b"
            r"(?:\s*[,(.]|\s+(?:med|with|org|på|for|til|mit|avec|con)\s|$)",
            text, re.I,
        )
        if m:
            fields["name"] = m.group(1).strip().rstrip(",.")

    # --- Supplier invoice: extract supplier name and amount ---
    if task_type == TaskType.CREATE_SUPPLIER_INVOICE:
        m = re.search(
            r"(?:leverandør(?:en)?|supplier|fournisseur|lieferant|proveedor)\s+"
            r"([A-ZÆØÅ\u00C0-\u024F][\w\s]*?(?:AS|ASA|SA|GmbH|Ltd|Inc|Corp|AB|ApS|AG|SRL|SARL)?)\b"
            r"(?:\s*[,(.]|\s+(?:med|with|org|på|for|til)\s|$)",
            text, re.I,
        )
        if m:
            fields["supplier_name"] = m.group(1).strip().rstrip(",.")
        # Amount
        m = re.search(r"(\d+[\d\s.,]*)\s*(?:kr|NOK)", text, re.I)
        if m:
            amt_str = m.group(1).replace(",", ".").replace(" ", "")
            try:
                fields["amount_including_vat"] = float(amt_str)
            except ValueError:
                pass

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

    # --- General date extraction (invoice_date, start_date, etc.) ---
    # ISO dates: "dato/date 2026-03-21" or "fakturadato 2026-03-21"
    if "invoice_date" not in fields and task_type in (
        TaskType.CREATE_INVOICE, TaskType.INVOICE_EXISTING_CUSTOMER, TaskType.INVOICE_WITH_PAYMENT,
    ):
        m = re.search(r"(?:fakturadato|invoice\s*date|Rechnungsdatum|fecha\s*(?:de\s*)?factura|date\s*(?:de\s*)?facture|data\s*(?:da\s*)?fatura)\s*:?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
        if m:
            fields["invoice_date"] = m.group(1)
        else:
            # European text date: "21. mars 2026", "21 de marzo de 2026", "21 März 2026"
            _MONTH_MAP_GENERAL = {
                "januar": "01", "january": "01", "janvier": "01", "enero": "01", "janeiro": "01",
                "februar": "02", "february": "02", "février": "02", "febrero": "02", "fevereiro": "02",
                "mars": "03", "march": "03", "marzo": "03", "março": "03", "märz": "03", "marz": "03",
                "april": "04", "avril": "04", "abril": "04",
                "mai": "05", "may": "05", "mayo": "05", "maio": "05",
                "juni": "06", "june": "06", "juin": "06", "junio": "06", "junho": "06",
                "juli": "07", "july": "07", "juillet": "07", "julio": "07", "julho": "07",
                "august": "08", "août": "08", "aout": "08", "agosto": "08",
                "september": "09", "septembre": "09", "septiembre": "09", "setembro": "09",
                "oktober": "10", "october": "10", "octobre": "10", "octubre": "10", "outubro": "10",
                "november": "11", "novembre": "11", "noviembre": "11", "novembro": "11",
                "desember": "12", "december": "12", "décembre": "12", "decembre": "12",
                "diciembre": "12", "dezembro": "12", "dezember": "12",
            }
            m = re.search(r"(\d{1,2})\.?\s+(?:de\s+)?([A-Za-zÀ-ÿ]+)\s+(?:de\s+)?(\d{4})", text, re.I)
            if m:
                day = int(m.group(1))
                month_str = m.group(2).lower()
                year = m.group(3)
                month_num = _MONTH_MAP_GENERAL.get(month_str)
                if month_num:
                    fields["invoice_date"] = f"{year}-{month_num}-{day:02d}"

    # --- Bank account number ---
    if "bank_account_number" not in fields:
        m = re.search(r"(?:bankkonto|bank\s*account|kontonummer|Bankverbindung|cuenta\s*bancaria|compte\s*bancaire)\s*(?:nummer|number|nr\.?)?\s*:?\s*([\d\s.-]{6,})", text, re.I)
        if m:
            fields["bank_account_number"] = m.group(1).replace(" ", "").replace("-", "").replace(".", "")

    # --- National identity number (personnummer) ---
    if "national_identity_number" not in fields and task_type in (TaskType.CREATE_EMPLOYEE, TaskType.UPDATE_EMPLOYEE):
        m = re.search(r"(?:personnummer|fødselsnummer|national\s*(?:identity|id)\s*(?:number)?|SSN|DNI|CPF|NIF)\s*:?\s*(\d{11})", text, re.I)
        if m:
            fields["national_identity_number"] = m.group(1)

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


def _detect_batch(prompt: str, task_type: TaskType) -> list[dict] | None:
    """Detect batch/multi-entity patterns like 'Create three departments: X, Y, Z'.

    Returns a list of field dicts (one per entity) or None if not a batch.
    """
    # Only handle CREATE tasks for batching
    _BATCH_TYPES = {
        TaskType.CREATE_DEPARTMENT: "name",
        TaskType.CREATE_EMPLOYEE: "name",
        TaskType.CREATE_CUSTOMER: "name",
        TaskType.CREATE_PRODUCT: "name",
        TaskType.CREATE_PROJECT: "name",
    }
    if task_type not in _BATCH_TYPES:
        return None

    # Pattern: "create N entities: X, Y, Z" or "create N entities: X, Y and Z"
    m = re.search(
        r"(?:opprett|create|lag|erstellen|créer|crear|criar)\s+"
        r"(?:tre|three|drei|trois|tres|três|3|fire|four|vier|quatre|cuatro|quatro|4|"
        r"fem|five|fünf|cinq|cinco|5|seks|six|sechs|6|sju|seven|sieben|sept|siete|sete|7|"
        r"åtte|eight|acht|huit|ocho|oito|8|ni|nine|neun|neuf|nueve|nove|9|"
        r"ti|ten|zehn|dix|diez|dez|10|to|two|zwei|deux|dos|dois|2)\s+"
        r"(?:nye?\s+)?"
        r"(?:avdeling\w*|department\w*|département\w*|departamento\w*|abteilung\w*|"
        r"ansatt\w*|employee\w*|kunde\w*|customer\w*|produkt\w*|product\w*|"
        r"prosjekt\w*|project\w*)\s*[:\-]\s*"
        r"(.+)",
        prompt, re.I | re.DOTALL,
    )
    if not m:
        return None

    items_text = m.group(1).strip()
    # Split by comma or " og "/" and "/" und "/" et "/" y "/" e "
    items = re.split(r"\s*(?:,\s*(?:og|and|und|et|y|e)\s+|,\s+|\s+og\s+|\s+and\s+|\s+und\s+|\s+et\s+|\s+y\s+|\s+e\s+)\s*", items_text)
    items = [item.strip().rstrip(".,") for item in items if item.strip()]

    if len(items) < 2:
        return None

    name_field = _BATCH_TYPES[task_type]
    return [{name_field: item} for item in items]


async def _classify_rule_based(prompt: str, files: Optional[list[dict]] = None) -> TaskClassification:
    """Simple keyword-based classification with regex field extraction — no LLM required."""
    text = prompt.lower()
    for task_type, patterns in _KEYWORD_MAP:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Check for batch/multi-entity patterns
                batch_items = _detect_batch(prompt, task_type)
                if batch_items:
                    # Return list of classifications for batch processing
                    classifications = []
                    for item_fields in batch_items:
                        base_fields = _extract_fields_rule_based(task_type, prompt)
                        base_fields.update(item_fields)
                        classifications.append(TaskClassification(
                            task_type=task_type,
                            confidence=0.6,
                            fields=base_fields,
                            raw_prompt=prompt,
                        ))
                    return classifications  # type: ignore[return-value]

                fields = _extract_fields_rule_based(task_type, prompt)
                return TaskClassification(
                    task_type=task_type,
                    confidence=0.6,
                    fields=fields,
                    raw_prompt=prompt,
                )

    # Last resort: single-word heuristic — NEVER return UNKNOWN if there's any signal
    _LAST_RESORT_WORDS = [
        (["lønn", "lonn", "payroll", "paie", "gehalt", "nómina", "salaire", "lønnskjøring", "lonnskjoring", "salary"], TaskType.RUN_PAYROLL),
        (["dimensjon", "dimension", "buchhaltungsdimension", "kostsenter", "kostenstelle", "cost center", "fri dimensjon", "custom dimension", "dimensión", "dimensão", "dimensione", "lønnsdimensjon", "lonnsdimensjon"], TaskType.CREATE_DIMENSION_VOUCHER),
        (["leverandørfaktura", "leverandorfaktura", "inngående faktura", "inngaaende faktura", "eingangsrechnung", "supplier invoice", "vendor invoice", "lieferantenrechnung", "facture fournisseur", "factura de proveedor", "fatura de fornecedor", "rechnung vom lieferanten", "rechnung des lieferanten", "facture du fournisseur"], TaskType.CREATE_SUPPLIER_INVOICE),
        (["leverandør", "supplier", "fournisseur", "lieferant", "lieferanten", "proveedor", "fornecedor"], TaskType.CREATE_SUPPLIER),
        (["bankavsteming", "reconcil", "rapprochement", "rapprocher", "rapprochez", "relevé bancaire", "releve bancaire", "bancaire", "abgleich"], TaskType.BANK_RECONCILIATION),
        (["faktura", "invoice", "factura", "rechnung", "facture", "fatura"], TaskType.CREATE_INVOICE),
        (["ansatt", "tilsett", "employee", "empleado", "mitarbeiter", "employé", "funcionário"], TaskType.CREATE_EMPLOYEE),
        (["kunde", "customer", "client", "cliente", "kunden"], TaskType.CREATE_CUSTOMER),
        (["avdeling", "department", "abteilung", "département", "departamento"], TaskType.CREATE_DEPARTMENT),
        (["modul", "module", "aktiver", "activate", "activar", "ativar", "attivare", "activer", "aktivieren"], TaskType.ENABLE_MODULE),
        (["prosjekt", "project", "projekt", "projet", "proyecto"], TaskType.CREATE_PROJECT),
        (["produkt", "product", "produit", "producto", "produto"], TaskType.CREATE_PRODUCT),
        (["timer", "hours", "timesheet", "timeliste", "stunden", "heures", "horas"], TaskType.LOG_HOURS),
        (["reiseregning", "reiserekning", "travel expense", "reisekosten", "frais de voyage"], TaskType.CREATE_TRAVEL_EXPENSE),
        (["kontaktperson", "contact", "contacto", "contato"], TaskType.CREATE_CONTACT),
        (["betaling", "payment", "innbetaling", "pago", "zahlung", "paiement"], TaskType.REGISTER_PAYMENT),
        (["kreditnota", "credit note", "gutschrift", "avoir"], TaskType.CREATE_CREDIT_NOTE),
        (["bankavsteming", "reconcil", "avstem", "kontoabstimmung", "conciliación", "conciliação", "riconciliazione", "rapprochement", "rapprocher", "rapprochez", "relevé bancaire", "releve bancaire", "bancaire", "afstemming", "bankafstemming", "bankabstimmung"], TaskType.BANK_RECONCILIATION),
        (["månedsslutt", "maanedsslutt", "month-end", "monatsabschluss", "clôture mensuelle", "cierre mensual", "periodisering", "periodificación", "depreciación mensual", "fechamento mensal", "chiusura mensile"], TaskType.MONTH_END_CLOSING),
        (["årsavslut", "arsavslut", "aarsavslut", "årsoppgjør", "arsoppgjor", "aarsoppgjor", "year-end", "encerramento", "chiusura", "cierre anual", "jahresabschluss", "clôture annuelle", "bokslut"], TaskType.YEAR_END_CLOSING),
        (["korriger", "correct error", "feilrett", "corrigir", "correggere", "corriger", "corregir", "korrigieren", "fehlbuchung", "feilpostering", "erreur comptable", "error contable", "erro contábil"], TaskType.ERROR_CORRECTION),
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
# Unified classifier dispatch
# ---------------------------------------------------------------------------

async def classify(prompt: str, files: Optional[list[dict]] = None) -> TaskClassification:
    """Route to the appropriate classifier based on LLM_MODE.

    Flow: hard overrides → rule-based first (instant) → if confident, skip LLM → else LLM.
    """
    from classifier import _post_process_fields, _normalize_fields, _extract_fields_generic

    # STEP 0: Hard overrides for known T3 misclassifications
    p_lower = prompt.lower()
    has_csv = False
    if files:
        for f in files:
            fname = (f.get("name") or f.get("filename") or "").lower()
            mime = (f.get("mime_type") or "").lower()
            if fname.endswith(".csv") or "csv" in mime:
                has_csv = True
                break
    if not has_csv and ("csv" in p_lower or ".csv" in p_lower):
        has_csv = True

    override_type = None
    # CSV + bank signals → BANK_RECONCILIATION (fixes French bank recon misclassification)
    bank_signals = ["banque", "bancaire", "bank", "konto", "compte", "relevé",
                    "releve", "solde", "transact", "kontoutskrift", "kontoauszug",
                    "rapproch", "reconcil", "avstem", "abgleich"]
    if has_csv and any(sig in p_lower for sig in bank_signals):
        override_type = TaskType.BANK_RECONCILIATION
    # German: "Rechnung" + supplier signal → REGISTER_SUPPLIER_INVOICE
    elif "rechnung" in p_lower and any(s in p_lower for s in [
        "lieferant", "zulieferer", "vom lieferant", "des lieferant",
        "von lieferant", "eingang",
    ]):
        override_type = TaskType.REGISTER_SUPPLIER_INVOICE
    # French: "facture" + "fournisseur" → REGISTER_SUPPLIER_INVOICE
    elif "facture" in p_lower and "fournisseur" in p_lower:
        override_type = TaskType.REGISTER_SUPPLIER_INVOICE

    if override_type:
        fields = _extract_fields_generic(prompt, override_type)
        fields = _post_process_fields(override_type, fields)
        fields = _normalize_fields(override_type, fields)
        log("INFO", "Hard override classification",
            task_type=str(override_type), trigger="misclassification_fix")
        return TaskClassification(
            task_type=override_type,
            confidence=0.95,
            fields=fields,
            raw_prompt=prompt,
        )

    # STEP 1: Always run rule-based first (instant, <1ms)
    rule_result = await _classify_rule_based(prompt, files)

    # Handle batch from rule-based
    if isinstance(rule_result, list):
        for r in rule_result:
            r.fields = _post_process_fields(r.task_type, r.fields)
            r.fields = _normalize_fields(r.task_type, r.fields)
        return rule_result

    # STEP 2: If rule-based is confident, use it directly (skip LLM)
    if rule_result.task_type != TaskType.UNKNOWN and rule_result.confidence >= 0.5:
        rule_result.fields = _post_process_fields(rule_result.task_type, rule_result.fields)
        rule_result.fields = _normalize_fields(rule_result.task_type, rule_result.fields)
        log("INFO", "Rule-based classifier confident, skipping LLM",
            task_type=str(rule_result.task_type), confidence=rule_result.confidence)
        # Still check for batch
        if LLM_MODE != "none":
            batch_items = _detect_batch(prompt, rule_result.task_type)
            if batch_items:
                classifications = []
                for item_fields in batch_items:
                    base_fields = dict(rule_result.fields)
                    base_fields.update(item_fields)
                    base_fields = _post_process_fields(rule_result.task_type, base_fields)
                    base_fields = _normalize_fields(rule_result.task_type, base_fields)
                    classifications.append(TaskClassification(
                        task_type=rule_result.task_type,
                        confidence=rule_result.confidence,
                        fields=base_fields,
                        raw_prompt=prompt,
                    ))
                log("INFO", "Rule-based result expanded to batch", count=len(classifications))
                return classifications  # type: ignore[return-value]
        return rule_result

    # STEP 3: Low confidence or UNKNOWN → fall through to LLM
    if LLM_MODE == "gemini":
        from classifier import classify_task
        result = await classify_task(prompt, files)  # already applies _post_process_fields
    elif LLM_MODE == "claude":
        result = await _classify_with_claude(prompt, files)
    else:
        # Already tried rule-based, just return what we got
        result = rule_result

    # Handle batch from LLM
    if isinstance(result, list):
        for r in result:
            r.fields = _post_process_fields(r.task_type, r.fields)
            r.fields = _normalize_fields(r.task_type, r.fields)
        return result

    # Apply post-processing and normalization to Claude and rule-based paths
    if LLM_MODE != "gemini":
        result.fields = _post_process_fields(result.task_type, result.fields)
        result.fields = _normalize_fields(result.task_type, result.fields)

    # For LLM classifiers: check if prompt is actually a batch
    if not isinstance(result, list) and LLM_MODE != "none":
        batch_items = _detect_batch(prompt, result.task_type)
        if batch_items:
            classifications = []
            for item_fields in batch_items:
                base_fields = dict(result.fields)
                base_fields.update(item_fields)
                base_fields = _post_process_fields(result.task_type, base_fields)
                base_fields = _normalize_fields(result.task_type, base_fields)
                classifications.append(TaskClassification(
                    task_type=result.task_type,
                    confidence=result.confidence,
                    fields=base_fields,
                    raw_prompt=prompt,
                ))
            log("INFO", "LLM result expanded to batch", count=len(classifications))
            return classifications  # type: ignore[return-value]

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
    _request_counter += 1
    req_num = _request_counter
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

    prompt = body.get("prompt", "") or ""
    # Ensure prompt is a string and handle edge cases
    if not isinstance(prompt, str):
        prompt = str(prompt)
    # Truncate extremely long prompts to avoid LLM token waste / timeouts
    MAX_PROMPT_LEN = 10000
    if len(prompt) > MAX_PROMPT_LEN:
        log("WARNING", "Prompt truncated", original_len=len(prompt), max_len=MAX_PROMPT_LEN)
        prompt = prompt[:MAX_PROMPT_LEN]
    files = body.get("files", []) or []
    creds = body.get("tripletex_credentials", {}) or {}

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
    classification = None
    # Overall timeout: bail gracefully before Cloud Run's 300s hard kill
    TASK_TIMEOUT = 270  # seconds

    async def _classify_and_execute():
        nonlocal result, task_type, classification
        # 1. Classify the task
        classification = await classify(prompt, files)

        from executor import execute_task

        # Handle batch classifications (list of tasks)
        if isinstance(classification, list):
            MAX_BATCH = 10
            task_type = "BATCH"
            if len(classification) > MAX_BATCH:
                log("WARNING", "Batch too large, capping",
                    original=len(classification), cap=MAX_BATCH)
                classification = classification[:MAX_BATCH]
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
            task_type = classification.task_type.value if hasattr(classification.task_type, 'value') else str(classification.task_type)
            log("INFO", "Classified task",
                task_type=task_type,
                confidence=getattr(classification, "confidence", None),
                llm_mode=LLM_MODE,
                fields=classification.fields)

            # 2. Execute the task
            result = await execute_task(classification, client)
            log("INFO", "Task executed", result_keys=list(result.keys()) if isinstance(result, dict) else None)

    try:
        await asyncio.wait_for(_classify_and_execute(), timeout=TASK_TIMEOUT)
    except asyncio.TimeoutError:
        log("ERROR", "Task timed out", timeout=TASK_TIMEOUT, task_type=task_type)
        result = {"success": False, "error": f"Task timed out after {TASK_TIMEOUT}s"}
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

    elapsed = time.monotonic() - start
    log("INFO", "Request complete", elapsed_seconds=round(elapsed, 2))

    # --- Human-readable request summary ---
    sep = "\u2550" * 60
    success = isinstance(result, dict) and result.get("success", False)
    status_str = "SUCCESS" if success else "FAILED"
    if not success and isinstance(result, dict) and result.get("error"):
        status_str += f" \u2014 {result['error']}"

    conf_str = ""
    fields_str = "{}"
    if classification is not None and not isinstance(classification, list):
        conf_str = f" (confidence: {classification.confidence})" if hasattr(classification, "confidence") and classification.confidence is not None else ""
        fields_str = json.dumps(classification.fields, ensure_ascii=False, default=str) if classification.fields else "{}"
    elif isinstance(classification, list):
        fields_str = f"[{len(classification)} sub-tasks]"

    detail_lines = ""
    if success and isinstance(result, dict):
        details = {k: v for k, v in result.items() if k != "success" and k != "batch_results"}
        if details:
            detail_lines = "\n  " + "\n  ".join(f"{k}: {v}" for k, v in details.items())

    summary = (
        f"\n{sep}\n"
        f"REQUEST #{req_num} | {elapsed:.1f}s | {LLM_MODE}\n"
        f"PROMPT: \"{prompt[:100]}{'...' if len(prompt) > 100 else ''}\"\n"
        f"CLASSIFIED: {task_type or 'N/A'}{conf_str}\n"
        f"FIELDS: {fields_str}\n"
        f"RESULT: {status_str}{detail_lines}\n"
        f"API CALLS: {client.api_call_count} | ERRORS: {client.error_count}\n"
        f"{sep}"
    )
    print(summary, flush=True)

    # Always return {"status":"completed"} — the competition grader requires it.
    # Include details for our debugging.
    response = {"status": "completed"}
    if task_type:
        response["task_type"] = task_type.value if hasattr(task_type, 'value') else str(task_type)
    if isinstance(result, dict):
        response["details"] = result
        # Mirror success at top level for grader compatibility
        if "success" in result:
            response["success"] = result["success"]
    return JSONResponse(response)
