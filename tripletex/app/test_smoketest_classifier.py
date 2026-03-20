"""Smoke-test for rule-based classifier functions (~250 test cases).

Tests:
  - _classify_with_keywords (classifier.py): keyword matching with anti_keywords
  - _last_resort_classify (classifier.py): single-word heuristic fallback
  - _classify_rule_based (main.py): regex-based classification + _LAST_RESORT_WORDS

Run: python test_smoketest_classifier.py
"""
import os
import sys
import asyncio

# Force rule-based mode — no LLM backends
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_types import TaskType
from classifier import _classify_with_keywords, _last_resort_classify

# _classify_rule_based is async
from main import _classify_rule_based

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------
_PASS = 0
_FAIL = 0
_ERRORS: list = []


def _check(label: str, result_type: TaskType, expected: TaskType):
    global _PASS, _FAIL
    if result_type == expected:
        _PASS += 1
    else:
        _FAIL += 1
        msg = f"  FAIL: {label} — got {result_type.value}, expected {expected.value}"
        _ERRORS.append(msg)
        print(msg)


# ---------------------------------------------------------------------------
# Test prompts per TaskType for _classify_rule_based (main.py)
# Covers 7 languages: nb, nn, en, de, fr, es, pt
# ---------------------------------------------------------------------------

RULE_BASED_CASES: list = [
    # ── CREATE_EMPLOYEE ──────────────────────────────────────────────────
    ("Opprett en ansatt med navn Ola Nordmann", TaskType.CREATE_EMPLOYEE),
    ("Opprett ein tilsett som heiter Kari Larsen", TaskType.CREATE_EMPLOYEE),
    ("Create an employee named John Smith", TaskType.CREATE_EMPLOYEE),
    ("Erstellen Sie einen Mitarbeiter namens Hans Müller", TaskType.CREATE_EMPLOYEE),
    ("Créer un employé appelé Pierre Dupont", TaskType.CREATE_EMPLOYEE),
    ("Crear un empleado llamado Juan García", TaskType.CREATE_EMPLOYEE),
    ("Criar um funcionário chamado João Silva", TaskType.CREATE_EMPLOYEE),

    # ── UPDATE_EMPLOYEE ──────────────────────────────────────────────────
    ("Oppdater ansatt Ola Nordmann med ny e-post", TaskType.UPDATE_EMPLOYEE),
    ("Endre tilsett Kari si adresse", TaskType.UPDATE_EMPLOYEE),
    ("Update employee John Smith's phone number", TaskType.UPDATE_EMPLOYEE),
    ("Ändern Sie den Mitarbeiter Hans Müller", TaskType.UPDATE_EMPLOYEE),
    ("Modifier l'employé Pierre Dupont", TaskType.UPDATE_EMPLOYEE),
    ("Actualizar el empleado Juan García", TaskType.UPDATE_EMPLOYEE),
    ("Atualizar o empregado João Silva", TaskType.UPDATE_EMPLOYEE),

    # ── DELETE_EMPLOYEE ──────────────────────────────────────────────────
    ("Slett ansatt Ola Nordmann", TaskType.DELETE_EMPLOYEE),
    ("Fjern tilsett Kari Larsen", TaskType.DELETE_EMPLOYEE),
    ("Delete employee John Smith", TaskType.DELETE_EMPLOYEE),
    ("Löschen Sie den Mitarbeiter Hans", TaskType.DELETE_EMPLOYEE),
    ("Supprimer l'employé Pierre Dupont", TaskType.DELETE_EMPLOYEE),
    ("Eliminar el empleado Juan García", TaskType.DELETE_EMPLOYEE),
    ("Excluir o funcionário João Silva", TaskType.DELETE_EMPLOYEE),

    # ── SET_EMPLOYEE_ROLES ───────────────────────────────────────────────
    ("Sett rolle for ansatt Ola Nordmann", TaskType.SET_EMPLOYEE_ROLES),
    ("Set role for employee John Smith as admin", TaskType.SET_EMPLOYEE_ROLES),
    ("Gi tilgang til ansatt Kari", TaskType.SET_EMPLOYEE_ROLES),
    ("Set employee role for Hans to manager", TaskType.SET_EMPLOYEE_ROLES),
    ("Set access for employee Pierre as user", TaskType.SET_EMPLOYEE_ROLES),
    ("Assign employee Juan as admin", TaskType.SET_EMPLOYEE_ROLES),
    ("Rolle for ansatt Kari bør endres", TaskType.SET_EMPLOYEE_ROLES),

    # ── CREATE_CUSTOMER ──────────────────────────────────────────────────
    ("Opprett en kunde med navn Acme AS", TaskType.CREATE_CUSTOMER),
    ("Opprett ein kunde som heiter Fjord Handel", TaskType.CREATE_CUSTOMER),
    ("Create a customer named Acme Corp", TaskType.CREATE_CUSTOMER),
    ("Erstellen Sie einen Kunden namens Müller GmbH", TaskType.CREATE_CUSTOMER),
    ("Créer un client appelé Dupont SA", TaskType.CREATE_CUSTOMER),
    ("Crear un cliente llamado García SL", TaskType.CREATE_CUSTOMER),
    ("Criar um cliente chamado Silva Lda", TaskType.CREATE_CUSTOMER),

    # ── UPDATE_CUSTOMER ──────────────────────────────────────────────────
    ("Oppdater kunde Acme AS med ny adresse", TaskType.UPDATE_CUSTOMER),
    ("Endre kunde Fjord Handel sin e-post", TaskType.UPDATE_CUSTOMER),
    ("Update customer Acme Corp phone number", TaskType.UPDATE_CUSTOMER),
    ("Ändern Sie den Kunden Müller GmbH", TaskType.UPDATE_CUSTOMER),
    ("Modifier le client Dupont SA", TaskType.UPDATE_CUSTOMER),
    ("Actualizar el cliente García SL", TaskType.UPDATE_CUSTOMER),
    ("Atualizar o cliente Silva Lda", TaskType.UPDATE_CUSTOMER),

    # ── DELETE_CUSTOMER ──────────────────────────────────────────────────
    ("Slett kunde Acme AS", TaskType.DELETE_CUSTOMER),
    ("Fjern kunde Fjord Handel", TaskType.DELETE_CUSTOMER),
    ("Delete customer Acme Corp", TaskType.DELETE_CUSTOMER),
    ("Löschen Sie den Kunden Müller GmbH", TaskType.DELETE_CUSTOMER),
    ("Supprimer le client Dupont SA", TaskType.DELETE_CUSTOMER),
    ("Eliminar el cliente García SL", TaskType.DELETE_CUSTOMER),
    ("Excluir o cliente Silva Lda", TaskType.DELETE_CUSTOMER),

    # ── FIND_CUSTOMER ────────────────────────────────────────────────────
    ("Finn kunde Acme", TaskType.FIND_CUSTOMER),
    ("Søk etter kunde med navn Fjord", TaskType.FIND_CUSTOMER),
    ("Find customer named Acme", TaskType.FIND_CUSTOMER),
    ("Suchen Sie den Kunden Müller", TaskType.FIND_CUSTOMER),
    ("Chercher le client Dupont", TaskType.FIND_CUSTOMER),
    ("Buscar el cliente García", TaskType.FIND_CUSTOMER),
    ("Procurar o cliente Silva", TaskType.FIND_CUSTOMER),

    # ── CREATE_PRODUCT ───────────────────────────────────────────────────
    ("Opprett et produkt med navn Widget", TaskType.CREATE_PRODUCT),
    ("Opprett eit produkt som heiter Gadget", TaskType.CREATE_PRODUCT),
    ("Create a product named Widget Pro", TaskType.CREATE_PRODUCT),
    ("Erstellen Sie ein Produkt namens Widget", TaskType.CREATE_PRODUCT),
    ("Créer un produit appelé Gadget", TaskType.CREATE_PRODUCT),
    ("Crear un producto llamado Widget", TaskType.CREATE_PRODUCT),
    ("Criar um produto chamado Gadget", TaskType.CREATE_PRODUCT),

    # ── CREATE_INVOICE ───────────────────────────────────────────────────
    # NOTE: "faktura for kunde" matches INVOICE_EXISTING_CUSTOMER in _KEYWORD_MAP
    # CREATE_INVOICE needs explicit "opprett" without "kunde" or other triggers
    ("Opprett en faktura med 3 stk Widget", TaskType.CREATE_INVOICE),
    ("Opprett en faktura med 5 stk varer", TaskType.CREATE_INVOICE),
    ("Create an invoice with 5 items", TaskType.CREATE_INVOICE),
    ("Erstellen Sie eine Rechnung mit Posten", TaskType.CREATE_INVOICE),
    ("Créer une facture avec des lignes", TaskType.CREATE_INVOICE),
    ("Crear una factura con productos", TaskType.CREATE_INVOICE),
    ("Criar uma fatura com itens", TaskType.CREATE_INVOICE),

    # ── INVOICE_EXISTING_CUSTOMER ────────────────────────────────────────
    ("Fakturer kunde Acme AS for 3 stk Widget", TaskType.INVOICE_EXISTING_CUSTOMER),
    ("Send faktura til kunde Fjord Handel", TaskType.INVOICE_EXISTING_CUSTOMER),
    ("Invoice customer Acme Corp for consulting", TaskType.INVOICE_EXISTING_CUSTOMER),
    ("Faktura til Ola Nordmann AS", TaskType.INVOICE_EXISTING_CUSTOMER),
    ("Faktura for kunde Bergen Bygg", TaskType.INVOICE_EXISTING_CUSTOMER),
    ("Lag faktura for kunde Acme AS", TaskType.INVOICE_EXISTING_CUSTOMER),
    ("Opprett faktura for kunde Fjord", TaskType.INVOICE_EXISTING_CUSTOMER),

    # ── REGISTER_PAYMENT ─────────────────────────────────────────────────
    ("Registrer innbetaling på faktura 1234", TaskType.REGISTER_PAYMENT),
    ("Registrer betaling for faktura 5678", TaskType.REGISTER_PAYMENT),
    ("Register payment on invoice 1234", TaskType.REGISTER_PAYMENT),
    ("Betaling for faktura 9999", TaskType.REGISTER_PAYMENT),
    ("Registrer innbetaling 5000 kr", TaskType.REGISTER_PAYMENT),
    ("Register payment of 5000 NOK", TaskType.REGISTER_PAYMENT),
    ("Registrer betaling på 10000 kr", TaskType.REGISTER_PAYMENT),

    # ── CREATE_CREDIT_NOTE ───────────────────────────────────────────────
    ("Opprett kreditnota for faktura 1234", TaskType.CREATE_CREDIT_NOTE),
    ("Lag kreditnota for faktura 5678", TaskType.CREATE_CREDIT_NOTE),
    ("Create a credit note for invoice 1234", TaskType.CREATE_CREDIT_NOTE),
    ("Erstellen Sie eine Gutschrift für Rechnung 1234", TaskType.CREATE_CREDIT_NOTE),
    ("Créer un avoir pour facture 1234", TaskType.CREATE_CREDIT_NOTE),
    ("Nota de crédito para factura 1234", TaskType.CREATE_CREDIT_NOTE),
    ("Kreditnota for faktura 42", TaskType.CREATE_CREDIT_NOTE),

    # ── INVOICE_WITH_PAYMENT ─────────────────────────────────────────────
    ("Opprett faktura med betaling for Acme", TaskType.INVOICE_WITH_PAYMENT),
    ("Lag faktura som er betalt for Fjord", TaskType.INVOICE_WITH_PAYMENT),
    ("Create invoice with payment for Acme Corp", TaskType.INVOICE_WITH_PAYMENT),
    ("Unbezahlte Rechnung mit Zahlung registrieren", TaskType.INVOICE_WITH_PAYMENT),
    ("Facture impayée med betaling", TaskType.INVOICE_WITH_PAYMENT),
    ("Invoice already paid for García SL", TaskType.INVOICE_WITH_PAYMENT),
    ("Faktura betalt for Acme", TaskType.INVOICE_WITH_PAYMENT),

    # ── CREATE_TRAVEL_EXPENSE ────────────────────────────────────────────
    ("Opprett reiseregning for Ola Nordmann", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Lag reiserekning for Kari Larsen", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Create a travel expense for John Smith", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Erstellen Sie eine Reisekostenabrechnung", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Créer des frais de voyage pour Pierre", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Crear gastos de viaje para Juan García", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Reiseregning til Bergen for Ola", TaskType.CREATE_TRAVEL_EXPENSE),

    # ── DELETE_TRAVEL_EXPENSE ────────────────────────────────────────────
    ("Slett reiseregning nummer 42", TaskType.DELETE_TRAVEL_EXPENSE),
    ("Fjern reiserekning for Kari", TaskType.DELETE_TRAVEL_EXPENSE),
    ("Delete travel expense number 42", TaskType.DELETE_TRAVEL_EXPENSE),
    ("Remove travel expense report 99", TaskType.DELETE_TRAVEL_EXPENSE),
    ("Slett reise for Ola Nordmann", TaskType.DELETE_TRAVEL_EXPENSE),
    ("Fjern reiseregning 55", TaskType.DELETE_TRAVEL_EXPENSE),
    ("Delete travel report for John", TaskType.DELETE_TRAVEL_EXPENSE),

    # ── CREATE_DEPARTMENT ────────────────────────────────────────────────
    ("Opprett en avdeling med navn Salg", TaskType.CREATE_DEPARTMENT),
    ("Opprett ei avdeling som heiter Økonomi", TaskType.CREATE_DEPARTMENT),
    ("Create a department named Sales", TaskType.CREATE_DEPARTMENT),
    ("Erstellen Sie eine Abteilung namens Vertrieb", TaskType.CREATE_DEPARTMENT),
    ("Créer un département appelé Ventes", TaskType.CREATE_DEPARTMENT),
    ("Crear un departamento llamado Ventas", TaskType.CREATE_DEPARTMENT),
    ("Criar um departamento chamado Vendas", TaskType.CREATE_DEPARTMENT),

    # ── UPDATE_DEPARTMENT ────────────────────────────────────────────────
    ("Oppdater avdeling Salg med ny leder", TaskType.UPDATE_DEPARTMENT),
    ("Endre avdeling Økonomi sitt navn", TaskType.UPDATE_DEPARTMENT),
    ("Update department Sales name", TaskType.UPDATE_DEPARTMENT),
    ("Ändern Sie die Abteilung Vertrieb", TaskType.UPDATE_DEPARTMENT),
    ("Modifier le département Ventes", TaskType.UPDATE_DEPARTMENT),
    ("Actualizar el departamento Ventas", TaskType.UPDATE_DEPARTMENT),
    ("Atualizar o departamento Vendas", TaskType.UPDATE_DEPARTMENT),

    # ── CREATE_PROJECT ───────────────────────────────────────────────────
    ("Opprett et prosjekt med navn Alpha", TaskType.CREATE_PROJECT),
    ("Opprett eit prosjekt som heiter Beta", TaskType.CREATE_PROJECT),
    ("Create a project named Alpha", TaskType.CREATE_PROJECT),
    ("Erstellen Sie ein Projekt namens Alpha", TaskType.CREATE_PROJECT),
    ("Créer un projet appelé Alpha", TaskType.CREATE_PROJECT),
    ("Crear un proyecto llamado Alpha", TaskType.CREATE_PROJECT),
    ("Criar um projeto chamado Alpha", TaskType.CREATE_PROJECT),

    # ── UPDATE_PROJECT ───────────────────────────────────────────────────
    ("Oppdater prosjekt Alpha med ny sluttdato", TaskType.UPDATE_PROJECT),
    ("Endre prosjekt Beta sin beskrivelse", TaskType.UPDATE_PROJECT),
    ("Update project Alpha end date", TaskType.UPDATE_PROJECT),
    ("Ändern Sie das Projekt Alpha", TaskType.UPDATE_PROJECT),
    ("Modifier le projet Alpha", TaskType.UPDATE_PROJECT),
    ("Actualizar el proyecto Alpha", TaskType.UPDATE_PROJECT),
    ("Oppdater prosjekt Gamma", TaskType.UPDATE_PROJECT),

    # ── DELETE_PROJECT ───────────────────────────────────────────────────
    ("Slett prosjekt Alpha", TaskType.DELETE_PROJECT),
    ("Slett prosjekt Beta fra systemet", TaskType.DELETE_PROJECT),
    ("Delete project Alpha", TaskType.DELETE_PROJECT),
    ("Löschen Sie das Projekt Alpha", TaskType.DELETE_PROJECT),
    ("Supprimer le projet Alpha", TaskType.DELETE_PROJECT),
    ("Eliminar el proyecto Alpha", TaskType.DELETE_PROJECT),
    ("Remove project Beta permanently", TaskType.DELETE_PROJECT),

    # ── PROJECT_WITH_CUSTOMER ────────────────────────────────────────────
    ("Opprett prosjekt for kunde Acme AS", TaskType.PROJECT_WITH_CUSTOMER),
    ("Prosjekt til kunde Fjord Handel", TaskType.PROJECT_WITH_CUSTOMER),
    ("Create a project for customer Acme Corp", TaskType.PROJECT_WITH_CUSTOMER),
    ("Projekt for Kunden Müller GmbH", TaskType.PROJECT_WITH_CUSTOMER),
    ("Projet pour client Dupont SA", TaskType.PROJECT_WITH_CUSTOMER),
    ("Proyecto para cliente García SL", TaskType.PROJECT_WITH_CUSTOMER),
    ("Prosjekt knyttet til kunde Fjord", TaskType.PROJECT_WITH_CUSTOMER),

    # ── PROJECT_BILLING ──────────────────────────────────────────────────
    ("Fakturer prosjekt Alpha", TaskType.PROJECT_BILLING),
    ("Fakturér prosjekt Beta", TaskType.PROJECT_BILLING),
    ("Faktur prosjekt Beta", TaskType.PROJECT_BILLING),
    ("Prosjekt Alpha må faktureres", TaskType.PROJECT_BILLING),
    ("Fakturer for prosjekt Gamma", TaskType.PROJECT_BILLING),
    ("Fakturering av prosjekt Delta", TaskType.PROJECT_BILLING),
    ("Fakturer prosjekt Epsilon", TaskType.PROJECT_BILLING),

    # ── CREATE_CONTACT ───────────────────────────────────────────────────
    ("Opprett kontaktperson for kunde Acme AS", TaskType.CREATE_CONTACT),
    ("Ny kontaktperson for Fjord Handel", TaskType.CREATE_CONTACT),
    ("Create a contact person for customer Acme", TaskType.CREATE_CONTACT),
    ("Add contact for customer Acme Corp", TaskType.CREATE_CONTACT),
    ("Crear un contacto para cliente García", TaskType.CREATE_CONTACT),
    ("Opprett kontaktperson for kunde Silva", TaskType.CREATE_CONTACT),
    ("Kontaktperson for Müller GmbH", TaskType.CREATE_CONTACT),

    # ── UPDATE_CONTACT ───────────────────────────────────────────────────
    ("Oppdater kontaktperson Ola Nordmann", TaskType.UPDATE_CONTACT),
    ("Endre kontaktperson for kunde Acme", TaskType.UPDATE_CONTACT),
    ("Update contact person John Smith", TaskType.UPDATE_CONTACT),
    ("Modifier le contact Pierre", TaskType.UPDATE_CONTACT),
    ("Actualizar el contacto Juan", TaskType.UPDATE_CONTACT),
    ("Atualizar o contato João", TaskType.UPDATE_CONTACT),
    ("Endre kontaktperson for Kari Larsen", TaskType.UPDATE_CONTACT),

    # ── LOG_HOURS ────────────────────────────────────────────────────────
    ("Logg 8 timer på prosjekt Alpha for Ola", TaskType.LOG_HOURS),
    ("Logg timer for prosjekt Beta", TaskType.LOG_HOURS),
    ("Log 4 hours on project Alpha for John", TaskType.LOG_HOURS),
    ("Erfassen Sie 6 Stunden auf Projekt Alpha", TaskType.LOG_HOURS),
    ("Enregistrer 5 heures sur le projet Alpha", TaskType.LOG_HOURS),
    ("Enter hours for project Alpha", TaskType.LOG_HOURS),
    ("Timesheet for prosjekt Alpha", TaskType.LOG_HOURS),

    # ── BANK_RECONCILIATION ──────────────────────────────────────────────
    ("Utfør bankavsteming for mars 2026", TaskType.BANK_RECONCILIATION),
    ("Avstem bank for Q1 2026", TaskType.BANK_RECONCILIATION),
    ("Perform bank reconciliation for March", TaskType.BANK_RECONCILIATION),
    ("Bankavstemming for konto 1920", TaskType.BANK_RECONCILIATION),
    ("Reconcile bank transactions for March", TaskType.BANK_RECONCILIATION),
    ("Rapprochement bancaire de mars", TaskType.BANK_RECONCILIATION),
    ("Bankavsteming for mars måned", TaskType.BANK_RECONCILIATION),

    # ── ERROR_CORRECTION ─────────────────────────────────────────────────
    ("Korriger feil i bilag 42", TaskType.ERROR_CORRECTION),
    ("Fiks feil i bilag 99", TaskType.ERROR_CORRECTION),
    ("Correct error in voucher 42", TaskType.ERROR_CORRECTION),
    ("Feil i bilag som må korrigeres", TaskType.ERROR_CORRECTION),
    ("Korriger postering med feil beløp", TaskType.ERROR_CORRECTION),
    ("Korriger feil i voucher 77", TaskType.ERROR_CORRECTION),
    ("Feil i bilag 88 korriger", TaskType.ERROR_CORRECTION),

    # ── YEAR_END_CLOSING ─────────────────────────────────────────────────
    ("Utfør årsavslutning for 2025", TaskType.YEAR_END_CLOSING),
    ("Årsoppgjør for regnskap 2025", TaskType.YEAR_END_CLOSING),
    ("Perform year-end closing for 2025", TaskType.YEAR_END_CLOSING),
    ("Jahresabschluss für 2025", TaskType.YEAR_END_CLOSING),
    ("Clôture annuelle pour 2025", TaskType.YEAR_END_CLOSING),
    ("Avslutt år 2025", TaskType.YEAR_END_CLOSING),
    ("Year-end closing procedures for 2025", TaskType.YEAR_END_CLOSING),

    # ── ENABLE_MODULE ────────────────────────────────────────────────────
    ("Aktiver modul Reiseregning", TaskType.ENABLE_MODULE),
    ("Slå på modul for lønn", TaskType.ENABLE_MODULE),
    ("Enable module Travel Expense", TaskType.ENABLE_MODULE),
    ("Aktivieren Sie das Modul Reisekosten", TaskType.ENABLE_MODULE),
    ("Activer le module Frais de voyage", TaskType.ENABLE_MODULE),
    ("Enable module for payroll", TaskType.ENABLE_MODULE),
    ("Aktiver modul for prosjekt", TaskType.ENABLE_MODULE),

    # ── CREATE_SUPPLIER ───────────────────────────────────────────────────
    ("Opprett en leverandør med navn Bygg AS", TaskType.CREATE_SUPPLIER),
    ("Create a supplier named Hardware Inc", TaskType.CREATE_SUPPLIER),
    ("Erstellen Sie einen Lieferant namens Müller", TaskType.CREATE_SUPPLIER),
    ("Créer un fournisseur appelé Dupont", TaskType.CREATE_SUPPLIER),
    ("Crear un proveedor llamado García", TaskType.CREATE_SUPPLIER),
    ("Criar um fornecedor chamado Silva", TaskType.CREATE_SUPPLIER),
    ("Registrer leverandør Nordic Parts", TaskType.CREATE_SUPPLIER),

    # ── UPDATE_SUPPLIER ───────────────────────────────────────────────────
    ("Oppdater leverandør Bygg AS med ny adresse", TaskType.UPDATE_SUPPLIER),
    ("Endre leverandør Nordic Parts sin e-post", TaskType.UPDATE_SUPPLIER),
    ("Update supplier Hardware Inc phone number", TaskType.UPDATE_SUPPLIER),
    ("Modifier le fournisseur Dupont", TaskType.UPDATE_SUPPLIER),
    ("Actualizar el proveedor García", TaskType.UPDATE_SUPPLIER),
    ("Ändern Sie den Lieferant Müller", TaskType.UPDATE_SUPPLIER),
    ("Atualizar o fornecedor Silva", TaskType.UPDATE_SUPPLIER),

    # ── DELETE_SUPPLIER ───────────────────────────────────────────────────
    ("Slett leverandør Bygg AS", TaskType.DELETE_SUPPLIER),
    ("Fjern leverandør Nordic Parts", TaskType.DELETE_SUPPLIER),
    ("Delete supplier Hardware Inc", TaskType.DELETE_SUPPLIER),
    ("Löschen Sie den Lieferant Müller", TaskType.DELETE_SUPPLIER),
    ("Supprimer le fournisseur Dupont", TaskType.DELETE_SUPPLIER),
    ("Eliminar el proveedor García", TaskType.DELETE_SUPPLIER),
    ("Remove supplier old vendor", TaskType.DELETE_SUPPLIER),

    # ── FIND_SUPPLIER ─────────────────────────────────────────────────────
    ("Finn leverandør Bygg AS", TaskType.FIND_SUPPLIER),
    ("Søk etter leverandør Nordic Parts", TaskType.FIND_SUPPLIER),
    ("Find supplier named Hardware Inc", TaskType.FIND_SUPPLIER),
    ("Suchen Sie den Lieferant Müller", TaskType.FIND_SUPPLIER),
    ("Chercher le fournisseur Dupont", TaskType.FIND_SUPPLIER),
    ("Buscar el proveedor García", TaskType.FIND_SUPPLIER),
    ("Finn leverandør med navn Silva", TaskType.FIND_SUPPLIER),

    # ── DELETE_CONTACT ────────────────────────────────────────────────────
    ("Slett kontaktperson Ola Nordmann", TaskType.DELETE_CONTACT),
    ("Fjern kontaktperson for kunde Acme", TaskType.DELETE_CONTACT),
    ("Delete contact person John Smith", TaskType.DELETE_CONTACT),
    ("Löschen Sie den contact Hans", TaskType.DELETE_CONTACT),
    ("Supprimer le contact Pierre", TaskType.DELETE_CONTACT),
    ("Eliminar el contacto Juan", TaskType.DELETE_CONTACT),
    ("Remove contact for customer Acme Corp", TaskType.DELETE_CONTACT),

    # ── DELETE_DEPARTMENT ─────────────────────────────────────────────────
    ("Slett avdeling Salg", TaskType.DELETE_DEPARTMENT),
    ("Fjern avdeling Økonomi", TaskType.DELETE_DEPARTMENT),
    ("Delete department Sales", TaskType.DELETE_DEPARTMENT),
    ("Löschen Sie die Abteilung Vertrieb", TaskType.DELETE_DEPARTMENT),
    ("Supprimer le département Ventes", TaskType.DELETE_DEPARTMENT),
    ("Eliminar el departamento Ventas", TaskType.DELETE_DEPARTMENT),
    ("Remove department HR permanently", TaskType.DELETE_DEPARTMENT),

    # ── DELETE_PRODUCT ────────────────────────────────────────────────────
    ("Slett produkt Widget", TaskType.DELETE_PRODUCT),
    ("Fjern produkt Gadget fra systemet", TaskType.DELETE_PRODUCT),
    ("Delete product Widget Pro", TaskType.DELETE_PRODUCT),
    ("Löschen Sie das Produkt Widget", TaskType.DELETE_PRODUCT),
    ("Supprimer le produit Gadget", TaskType.DELETE_PRODUCT),
    ("Eliminar el producto Widget", TaskType.DELETE_PRODUCT),
    ("Remove product old item", TaskType.DELETE_PRODUCT),

    # ── UPDATE_PRODUCT ────────────────────────────────────────────────────
    ("Oppdater produkt Widget med ny pris", TaskType.UPDATE_PRODUCT),
    ("Endre produkt Gadget sin beskrivelse", TaskType.UPDATE_PRODUCT),
    ("Update product Widget Pro price", TaskType.UPDATE_PRODUCT),
    ("Ändern Sie das Produkt Widget", TaskType.UPDATE_PRODUCT),
    ("Modifier le produit Gadget", TaskType.UPDATE_PRODUCT),
    ("Actualizar el producto Widget", TaskType.UPDATE_PRODUCT),
    ("Atualizar o produto Gadget", TaskType.UPDATE_PRODUCT),

    # ── REGISTER_SUPPLIER_INVOICE ─────────────────────────────────────────
    ("Registrer leverandørfaktura fra Bygg AS", TaskType.REGISTER_SUPPLIER_INVOICE),
    ("Bokfør inngående faktura fra Nordic Parts", TaskType.REGISTER_SUPPLIER_INVOICE),
    ("Register supplier invoice from Hardware Inc", TaskType.REGISTER_SUPPLIER_INVOICE),
    ("Book incoming invoice from vendor", TaskType.REGISTER_SUPPLIER_INVOICE),
    ("Enregistrer la facture fournisseur de Dupont", TaskType.REGISTER_SUPPLIER_INVOICE),
    ("Registrer leverandørfaktura nummer 42", TaskType.REGISTER_SUPPLIER_INVOICE),
    ("Eingangsrechnung von Müller GmbH", TaskType.REGISTER_SUPPLIER_INVOICE),

    # ── REVERSE_PAYMENT ───────────────────────────────────────────────────
    # NOTE: ERROR_CORRECTION regex also catches "reverse/reverser.*betaling/payment"
    # and "returnert/returned.*bank/betaling/payment", so use terms only in REVERSE_PAYMENT:
    # "bounced", "undo", "tilbakefør", "devolvido", "rückerstattet"
    ("Bounced payment for faktura 1234", TaskType.REVERSE_PAYMENT),
    ("Tilbakefør betaling for faktura 5678", TaskType.REVERSE_PAYMENT),
    ("Undo payment on invoice 1234", TaskType.REVERSE_PAYMENT),
    ("Bounced betaling på faktura 42", TaskType.REVERSE_PAYMENT),
    ("Rückerstattet zahlung für Rechnung 99", TaskType.REVERSE_PAYMENT),
    ("Pago devuelto para factura 55", TaskType.REVERSE_PAYMENT),
    ("Undo betaling på faktura 77", TaskType.REVERSE_PAYMENT),

    # ── RUN_PAYROLL ───────────────────────────────────────────────────────
    ("Kjør lønnskjøring for mars 2026", TaskType.RUN_PAYROLL),
    ("Utfør lønn for alle ansatte", TaskType.RUN_PAYROLL),
    ("Run payroll for March 2026", TaskType.RUN_PAYROLL),
    ("Execute payroll for all employees", TaskType.RUN_PAYROLL),
    ("Exécuter la paie pour mars", TaskType.RUN_PAYROLL),
    ("Lønnsutbetaling for mars", TaskType.RUN_PAYROLL),
    ("Kjør lønn for mars måned", TaskType.RUN_PAYROLL),

    # ── UPDATE_TRAVEL_EXPENSE ─────────────────────────────────────────────
    ("Oppdater reiseregning nummer 42", TaskType.UPDATE_TRAVEL_EXPENSE),
    ("Endre reiseregning for Ola Nordmann", TaskType.UPDATE_TRAVEL_EXPENSE),
    ("Update travel expense report 42", TaskType.UPDATE_TRAVEL_EXPENSE),
    ("Modify travel expense for John Smith", TaskType.UPDATE_TRAVEL_EXPENSE),
    ("Oppdater reiserekning for Kari", TaskType.UPDATE_TRAVEL_EXPENSE),
    ("Endre reiseregning 55 med nytt beløp", TaskType.UPDATE_TRAVEL_EXPENSE),
    ("Actualizar los gastos de viaje para Juan", TaskType.UPDATE_TRAVEL_EXPENSE),

    # ── CREATE_DIMENSION_AND_VOUCHER ──────────────────────────────────────
    ("Opprett regnskapsdimensjon for prosjekt Alpha", TaskType.CREATE_DIMENSION_AND_VOUCHER),
    ("Lag fri dimensjon med verdier", TaskType.CREATE_DIMENSION_AND_VOUCHER),
    ("Create accounting dimension and voucher", TaskType.CREATE_DIMENSION_AND_VOUCHER),
    ("Opprett dimensjon med verdiene A og B og bokfør bilag", TaskType.CREATE_DIMENSION_AND_VOUCHER),
    ("Konteringsdimensjon for avdeling Salg", TaskType.CREATE_DIMENSION_AND_VOUCHER),
    ("Free dimension with values X and Y", TaskType.CREATE_DIMENSION_AND_VOUCHER),
    ("Registrer regnskapsdimensjon og bilag", TaskType.CREATE_DIMENSION_AND_VOUCHER),
]

# ---------------------------------------------------------------------------
# Disambiguation test cases — tricky edge cases
# ---------------------------------------------------------------------------

DISAMBIGUATION_CASES: list = [
    # register_payment vs invoice_with_payment
    ("Registrer innbetaling på faktura 1234 med 5000 kr", TaskType.REGISTER_PAYMENT),
    ("Opprett faktura med betaling for Acme AS", TaskType.INVOICE_WITH_PAYMENT),

    # enable_module vs travel_expense — "Aktiver modul Reiseregning" = ENABLE_MODULE
    ("Aktiver modul Reiseregning", TaskType.ENABLE_MODULE),
    ("Opprett reiseregning for Ola Nordmann til Bergen", TaskType.CREATE_TRAVEL_EXPENSE),

    # project vs project_with_customer
    ("Opprett prosjekt Alpha", TaskType.CREATE_PROJECT),
    ("Opprett prosjekt Alpha for kunde Acme AS", TaskType.PROJECT_WITH_CUSTOMER),

    # delete vs create
    ("Slett ansatt Ola Nordmann", TaskType.DELETE_EMPLOYEE),
    ("Slett prosjekt Alpha", TaskType.DELETE_PROJECT),
    ("Slett reiseregning 42", TaskType.DELETE_TRAVEL_EXPENSE),

    # contact create vs update
    ("Opprett kontaktperson for kunde Acme AS", TaskType.CREATE_CONTACT),
    ("Oppdater kontaktperson Ola", TaskType.UPDATE_CONTACT),

    # customer: create vs find vs delete vs update
    ("Opprett en kunde med navn Acme", TaskType.CREATE_CUSTOMER),
    ("Finn kunde Acme", TaskType.FIND_CUSTOMER),
    ("Slett kunde Acme", TaskType.DELETE_CUSTOMER),
    ("Oppdater kunde Acme med ny e-post", TaskType.UPDATE_CUSTOMER),

    # employee: create vs update vs delete
    ("Opprett ansatt Ola Nordmann", TaskType.CREATE_EMPLOYEE),
    ("Oppdater ansatt Ola Nordmann", TaskType.UPDATE_EMPLOYEE),
    ("Slett ansatt Ola Nordmann fra systemet", TaskType.DELETE_EMPLOYEE),

    # invoice ambiguity: credit note vs plain invoice
    ("Opprett kreditnota for faktura 42", TaskType.CREATE_CREDIT_NOTE),

    # project billing regex
    ("Fakturer prosjekt Alpha", TaskType.PROJECT_BILLING),

    # travel: create vs delete
    ("Reiseregning for Ola til Bergen", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Slett reiseregning for Ola", TaskType.DELETE_TRAVEL_EXPENSE),

    # department: create vs update
    ("Opprett avdeling Salg", TaskType.CREATE_DEPARTMENT),
    ("Oppdater avdeling Salg", TaskType.UPDATE_DEPARTMENT),

    # Roles disambiguation from update
    ("Sett rolle for ansatt Ola som admin", TaskType.SET_EMPLOYEE_ROLES),
    ("Rolle for ansatt Ola bør endres", TaskType.SET_EMPLOYEE_ROLES),
]

# ---------------------------------------------------------------------------
# _classify_with_keywords specific cases (classifier.py)
# ---------------------------------------------------------------------------

KEYWORD_CLASSIFIER_CASES: list = [
    # Basic keyword matches
    ("Opprett en ansatt med navn Ola", TaskType.CREATE_EMPLOYEE),
    ("Create an employee named John", TaskType.CREATE_EMPLOYEE),
    ("Slett ansatt Ola", TaskType.DELETE_EMPLOYEE),
    ("Delete employee John", TaskType.DELETE_EMPLOYEE),
    ("Oppdater ansatt Kari", TaskType.UPDATE_EMPLOYEE),
    ("Sett rolle for ansatt Ola", TaskType.SET_EMPLOYEE_ROLES),
    ("Opprett kunde Acme AS", TaskType.CREATE_CUSTOMER),
    ("Finn kunde Acme", TaskType.FIND_CUSTOMER),
    ("Opprett faktura for ny Acme", TaskType.CREATE_INVOICE),
    ("Registrer innbetaling på faktura 42", TaskType.REGISTER_PAYMENT),
    ("Opprett kreditnota for faktura 42", TaskType.CREATE_CREDIT_NOTE),
    ("Reiseregning for Ola til Bergen", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Slett reiseregning 42", TaskType.DELETE_TRAVEL_EXPENSE),
    ("Fakturer prosjekt Alpha", TaskType.PROJECT_BILLING),
    ("Bankavsteming for mars", TaskType.BANK_RECONCILIATION),
    ("Korriger feil i bilag 42", TaskType.ERROR_CORRECTION),
    ("Årsavslutning for 2025", TaskType.YEAR_END_CLOSING),
    ("Aktiver modul Reiseregning", TaskType.ENABLE_MODULE),
    ("Logg timer på prosjekt Alpha", TaskType.LOG_HOURS),
    # Anti-keyword: "slett" should prevent CREATE_EMPLOYEE match
    ("Slett ansatt Ola Nordmann fra systemet", TaskType.DELETE_EMPLOYEE),
    # Project + customer -> PROJECT_WITH_CUSTOMER
    ("Opprett prosjekt for kunde Acme AS", TaskType.PROJECT_WITH_CUSTOMER),
    # Multilingual keywords
    ("Crear un empleado llamado Juan", TaskType.CREATE_EMPLOYEE),
    ("Créer un client appelé Dupont", TaskType.CREATE_CUSTOMER),
    ("Gastos de viaje para Juan García", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Frais de voyage pour Pierre Dupont", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Despesas de viagem para João Silva", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Travel expense for John Smith", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Registrer betaling for faktura 1234", TaskType.REGISTER_PAYMENT),
    ("Invoice with payment for Acme Corp", TaskType.INVOICE_WITH_PAYMENT),
    ("Faktura med betaling for Acme AS", TaskType.INVOICE_WITH_PAYMENT),
    # Update contact
    ("Oppdater kontakt Ola Nordmann", TaskType.UPDATE_CONTACT),
    ("Endre kontaktperson for kunde", TaskType.UPDATE_CONTACT),
    ("Update contact for customer Acme", TaskType.UPDATE_CONTACT),
    # Delete customer
    ("Slett kunde Acme AS", TaskType.DELETE_CUSTOMER),
    ("Delete customer Acme Corp", TaskType.DELETE_CUSTOMER),
    # Update department
    ("Oppdater avdeling Salg", TaskType.UPDATE_DEPARTMENT),
    ("Update department Sales", TaskType.UPDATE_DEPARTMENT),
    # Nynorsk forms
    ("Opprett ein tilsett som heiter Per", TaskType.CREATE_EMPLOYEE),
    ("Fjern tilsett Kari", TaskType.DELETE_EMPLOYEE),
    ("Endre tilsett Ola sin e-post", TaskType.UPDATE_EMPLOYEE),
    ("Reiserekning for Kari", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Slett reiserekning for Ola", TaskType.DELETE_TRAVEL_EXPENSE),
]

# ---------------------------------------------------------------------------
# _last_resort_classify specific cases (classifier.py)
# ---------------------------------------------------------------------------

LAST_RESORT_CASES: list = [
    # Single-word triggers for last resort
    ("Noe med faktura her", TaskType.CREATE_INVOICE),
    ("Something about an invoice", TaskType.CREATE_INVOICE),
    ("En ansatt trenger oppdatering", TaskType.CREATE_EMPLOYEE),
    ("New employee for the team", TaskType.CREATE_EMPLOYEE),
    ("Noe med kunde Acme", TaskType.CREATE_CUSTOMER),
    ("Something about customer records", TaskType.CREATE_CUSTOMER),
    ("Noe med prosjekt Alpha", TaskType.CREATE_PROJECT),
    ("Some product info needed", TaskType.CREATE_PRODUCT),
    ("Avdeling HR trenger endring", TaskType.CREATE_DEPARTMENT),
    ("Kreditnota trengs", TaskType.CREATE_CREDIT_NOTE),
    ("Reiseregning mangler", TaskType.CREATE_TRAVEL_EXPENSE),
    ("Timer på prosjekt", TaskType.LOG_HOURS),
    ("Bankavstemming trengs", TaskType.BANK_RECONCILIATION),
    ("Årsavslutning snart", TaskType.YEAR_END_CLOSING),
    ("Korriger denne posten", TaskType.ERROR_CORRECTION),
    ("Aktiver modul for regnskap", TaskType.ENABLE_MODULE),
    # Delete patterns in last resort
    ("Slett kunde Bergen AS", TaskType.DELETE_CUSTOMER),
    ("Slett ansatt fra listen", TaskType.DELETE_EMPLOYEE),
    ("Delete project old", TaskType.DELETE_PROJECT),
    ("Slett reise for Ola", TaskType.DELETE_TRAVEL_EXPENSE),
    # Update patterns in last resort
    ("Oppdater ansatt informasjon", TaskType.UPDATE_EMPLOYEE),
    ("Update customer details", TaskType.UPDATE_CUSTOMER),
    ("Oppdater prosjekt deadline", TaskType.UPDATE_PROJECT),
    ("Oppdater kontakt info", TaskType.UPDATE_CONTACT),
    ("Oppdater avdeling struktur", TaskType.UPDATE_DEPARTMENT),
    # Find
    ("Finn kunde Berg AS", TaskType.FIND_CUSTOMER),
    # Roles
    ("Endre rolle for ansatt", TaskType.SET_EMPLOYEE_ROLES),
    # Betaling -> INVOICE_WITH_PAYMENT (in classifier.py last resort)
    ("Noe om betaling", TaskType.INVOICE_WITH_PAYMENT),
    # Contact
    ("Kontaktperson for Acme", TaskType.CREATE_CONTACT),
]


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

def test_classify_rule_based():
    """Test _classify_rule_based (main.py) — regex-based async classifier."""
    print("\n=== _classify_rule_based (main.py) ===")
    all_cases = RULE_BASED_CASES + DISAMBIGUATION_CASES
    loop = asyncio.new_event_loop()
    for prompt, expected in all_cases:
        result = loop.run_until_complete(_classify_rule_based(prompt))
        _check(f"rule_based: {prompt[:60]}", result.task_type, expected)
    loop.close()
    print(f"  Subtotal: {len(all_cases)} cases")


def test_classify_with_keywords():
    """Test _classify_with_keywords (classifier.py) — keyword matching."""
    print("\n=== _classify_with_keywords (classifier.py) ===")
    for prompt, expected in KEYWORD_CLASSIFIER_CASES:
        result = _classify_with_keywords(prompt)
        _check(f"keywords: {prompt[:60]}", result.task_type, expected)
    print(f"  Subtotal: {len(KEYWORD_CLASSIFIER_CASES)} cases")


def test_last_resort_classify():
    """Test _last_resort_classify (classifier.py) — single-word heuristic."""
    print("\n=== _last_resort_classify (classifier.py) ===")
    for prompt, expected in LAST_RESORT_CASES:
        result = _last_resort_classify(prompt)
        _check(f"last_resort: {prompt[:60]}", result.task_type, expected)
    print(f"  Subtotal: {len(LAST_RESORT_CASES)} cases")


def test_coverage():
    """Ensure every TaskType (except UNKNOWN) has at least one test prompt."""
    print("\n=== Coverage check ===")
    all_cases = (
        RULE_BASED_CASES
        + DISAMBIGUATION_CASES
        + KEYWORD_CLASSIFIER_CASES
        + LAST_RESORT_CASES
    )
    covered = {expected for _, expected in all_cases}
    all_types = {t for t in TaskType if t != TaskType.UNKNOWN}
    missing = all_types - covered
    if missing:
        for t in sorted(missing, key=lambda x: x.value):
            msg = f"  FAIL: No test prompt for {t.value}"
            print(msg)
            global _FAIL
            _FAIL += 1
            _ERRORS.append(msg)
    else:
        global _PASS
        _PASS += 1
        print("  All TaskType values covered!")


if __name__ == "__main__":
    print("=" * 60)
    print("Classifier Smoke Test")
    print("=" * 60)

    test_classify_rule_based()
    test_classify_with_keywords()
    test_last_resort_classify()
    test_coverage()

    total = _PASS + _FAIL
    print("\n" + "=" * 60)
    print(f"RESULTS: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("\nFailed tests:")
        for e in _ERRORS:
            print(e)
    print("=" * 60)

    sys.exit(0 if _FAIL == 0 else 1)
