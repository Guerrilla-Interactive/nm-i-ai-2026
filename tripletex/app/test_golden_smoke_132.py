"""
Golden Smoke Test — 19 reconstructed real grader prompts from 2026-03-21.
Source: golden_grader_data.json (entries from 2026-03-21 excluding revision 00133).
Revisions covered: 00128, 00132, 00135, 00145.

Tests classifier only (no API calls) — verifies task_type classification.
Known misclassifications from production are marked with expected_correct_type.

Usage:
    python test_golden_smoke_132.py              # Test all 19
    python test_golden_smoke_132.py --verbose    # Show field extraction too
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
import time

# ---------------------------------------------------------------------------
# Reconstructed grader prompts (from 120-char previews + field context)
# ---------------------------------------------------------------------------

SMOKE_CASES: list[dict] = [
    # 1. FR project_with_customer — rev 00145
    {
        "id": 1,
        "lang": "fr",
        "revision": "00145",
        "prompt": (
            'Créez le projet "Migration Étoile" lié au client Étoile SARL (nº org. 964531161). '
            "Le chef de projet est Arthur Dubois (arthur.dubois@example.org)."
        ),
        "expected_type": "project_with_customer",
        "file_count": 0,
    },
    # 2. ES run_payroll — rev 00145
    {
        "id": 2,
        "lang": "es",
        "revision": "00145",
        "prompt": (
            "Ejecute la nómina de Fernando López (fernando.lopez@example.org) para este mes. "
            "El salario base es de 37850 NOK. Añada un bono de rendimiento."
        ),
        "expected_type": "run_payroll",
        "file_count": 0,
    },
    # 3. NO create_employee — rev 00135 (test probe)
    {
        "id": 3,
        "lang": "no",
        "revision": "00135",
        "prompt": "Opprett en ansatt med navn Test Person",
        "expected_type": "create_employee",
        "file_count": 0,
    },
    # 4. FR error_correction — rev 00132 — KNOWN MISCLASSIFICATION (was UNKNOWN)
    {
        "id": 4,
        "lang": "fr",
        "revision": "00132",
        "prompt": (
            "Nous avons découvert des erreurs dans le grand livre de janvier et février 2026. "
            "Vérifiez toutes les pièces et trouvez les 4 erreurs: un lancement incorrect du "
            "compte, une écriture en double, un montant erroné et une pièce manquante. "
            "Corrigez chaque erreur avec une pièce de correction."
        ),
        "expected_type": "error_correction",
        "known_misclassification": True,
        "production_type": "UNKNOWN",
        "file_count": 0,
    },
    # 5. PT error_correction — rev 00132 — KNOWN MISCLASSIFICATION (was UNKNOWN)
    {
        "id": 5,
        "lang": "pt",
        "revision": "00132",
        "prompt": (
            "Descobrimos erros no livro razão de janeiro e fevereiro de 2026. "
            "Revise todos os vouchers e encontre os 4 erros: um lançamento na conta errada, "
            "um lançamento duplicado, um montante incorreto e um voucher em falta. "
            "Corrija cada erro com um voucher de correção."
        ),
        "expected_type": "error_correction",
        "known_misclassification": True,
        "production_type": "UNKNOWN",
        "file_count": 0,
    },
    # 6. ES create_employee (with PDF) — rev 00132
    {
        "id": 6,
        "lang": "es",
        "revision": "00132",
        "prompt": (
            "Has recibido una carta de oferta (ver PDF adjunto) para un nuevo empleado. "
            "Completa la incorporacion: crea el empleado, asigna al departamento Produksjon "
            "y registra la fecha de nacimiento 1988-05-19."
        ),
        "expected_type": "create_employee",
        "file_count": 1,
    },
    # 7. FR run_payroll — rev 00132
    {
        "id": 7,
        "lang": "fr",
        "revision": "00132",
        "prompt": (
            "Exécutez la paie de Sarah Moreau (sarah.moreau@example.org) pour ce mois. "
            "Le salaire de base est de 56900 NOK. Ajoutez un bonus de 15800 NOK."
        ),
        "expected_type": "run_payroll",
        "file_count": 0,
    },
    # 8. PT year_end_closing — rev 00132
    {
        "id": 8,
        "lang": "pt",
        "revision": "00132",
        "prompt": (
            "Realize o encerramento anual simplificado de 2025: "
            "1) Calcule e registe a depreciação anual de três ativos: IT-utstyr (470650 kr, 5 anos, linear). "
            "2) Feche as contas de receita e despesa para o resultado do exercício."
        ),
        "expected_type": "year_end_closing",
        "file_count": 0,
    },
    # 9. NN error_correction — rev 00132 — KNOWN MISCLASSIFICATION (was CREATE_PROJECT)
    {
        "id": 9,
        "lang": "nn",
        "revision": "00132",
        "prompt": (
            "Totalkostnadene auka monaleg frå januar til februar 2026. "
            "Analyser hovudboka og finn dei tre kostnadskontoane med størst auke. "
            "Lag eit samandrag med kontonummer, kontonamn og endring i kroner."
        ),
        "expected_type": "error_correction",
        "known_misclassification": True,
        "production_type": "CREATE_PROJECT",
        "file_count": 0,
    },
    # 10. NN invoice_existing_customer — rev 00132
    {
        "id": 10,
        "lang": "nn",
        "revision": "00132",
        "prompt": (
            "Opprett ein faktura til kunden Fossekraft AS (org.nr 913494253) med tre produktlinjer: "
            "Skylagring (4508) til 1050 kr med 25% MVA, Hosting (3291) til 2400 kr med 25% MVA, "
            "og Datarådgivning (7812) til 8900 kr utan MVA."
        ),
        "expected_type": "invoice_existing_customer",
        "file_count": 0,
    },
    # 11. DE invoice_existing_customer — rev 00132
    {
        "id": 11,
        "lang": "de",
        "revision": "00132",
        "prompt": (
            "Einer Ihrer Kunden hat eine überfällige Rechnung. "
            "Finden Sie die überfällige Rechnung und buchen Sie eine Mahngebühr von 40 NOK. "
            "Belasten Sie das Konto 3900 und senden Sie die Mahnung."
        ),
        "expected_type": "invoice_existing_customer",
        "file_count": 0,
    },
    # 12. ES project_billing (compound) — rev 00132
    {
        "id": 12,
        "lang": "es",
        "revision": "00132",
        "prompt": (
            "Ejecute el ciclo de vida completo del proyecto 'Actualización Sistema Dorada' "
            "(Dorada SL, org. nº 888398554): "
            "1) El proyecto tiene un presupuesto de 460950 NOK. "
            "2) Asigne a Carlos García (carlos.garcia@example.org) como jefe de proyecto. "
            "3) Facture al cliente por el proyecto."
        ),
        "expected_type": "project_with_customer",  # "ciclo de vida del proyecto" = project lifecycle
        "file_count": 0,
    },
    # 13. PT register_supplier_invoice (with receipt) — rev 00132
    {
        "id": 13,
        "lang": "pt",
        "revision": "00132",
        "prompt": (
            "Precisamos da despesa de Kaffemøte deste recibo registada no departamento Utvikling. "
            "Use a conta de despesas correta e garanta que o IVA é calculado corretamente."
        ),
        "expected_type": "register_supplier_invoice",
        "file_count": 1,
    },
    # 14. ES project_billing (compound) — rev 00132 — KNOWN MISCLASSIFICATION (was INVOICE_EXISTING_CUSTOMER)
    {
        "id": 14,
        "lang": "es",
        "revision": "00132",
        "prompt": (
            'Registre 15 horas para Miguel Torres (miguel.torres@example.org) en la actividad '
            '"Design" del proyecto "Rediseño web" para Montaña SL (org. nº 828967452). '
            "Tarifa: 1800 NOK/h. Cree una factura al cliente basada en las horas registradas."
        ),
        "expected_type": "project_billing",
        "known_misclassification": True,
        "production_type": "INVOICE_EXISTING_CUSTOMER",
        "file_count": 0,
    },
    # 15. EN create_product — rev 00132
    {
        "id": 15,
        "lang": "en",
        "revision": "00132",
        "prompt": (
            'Create the product "Web Design" with product number 9780. '
            "The price is 30200 NOK excluding VAT, using the standard 25% VAT rate."
        ),
        "expected_type": "create_product",
        "file_count": 0,
    },
    # 16. ES create_employee (with PDF) — rev 00132
    {
        "id": 16,
        "lang": "es",
        "revision": "00132",
        "prompt": (
            "Has recibido un contrato de trabajo (ver PDF adjunto). "
            "Crea el empleado en Tripletex con todos los datos del contrato: "
            "nombre Pablo Torres, nacido el 1996-08-18, departamento Utvikling, "
            "número de identificación nacional 18089648714, cuenta bancaria 37262474683."
        ),
        "expected_type": "create_employee",
        "file_count": 1,
    },
    # 17. NO create_customer — rev 00132
    {
        "id": 17,
        "lang": "no",
        "revision": "00132",
        "prompt": (
            "Opprett kunden Snøhetta AS med organisasjonsnummer 969719878. "
            "Adressen er Industriveien 148, 2317 Hamar. E-post: post@snhetta.no."
        ),
        "expected_type": "create_customer",
        "file_count": 0,
    },
    # 18. PT error_correction — rev 00132 — KNOWN MISCLASSIFICATION (was CREATE_PROJECT)
    {
        "id": 18,
        "lang": "pt",
        "revision": "00132",
        "prompt": (
            "Os custos totais aumentaram significativamente de janeiro a fevereiro de 2026. "
            "Analise o livro razão e identifique as três contas de custos com maior aumento. "
            "Crie um resumo com número da conta, nome da conta e variação em coroas."
        ),
        "expected_type": "error_correction",
        "known_misclassification": True,
        "production_type": "CREATE_PROJECT",
        "file_count": 0,
    },
    # 19. ES month_end_closing — rev 00128 — KNOWN MISCLASSIFICATION (was UNKNOWN)
    {
        "id": 19,
        "lang": "es",
        "revision": "00128",
        "prompt": (
            "Realice el cierre mensual de marzo de 2026. "
            "Registre la periodificación (12500 NOK por mes de la cuenta 1720 a gasto). "
            "Calcule la depreciación mensual de los activos y cierre el período."
        ),
        "expected_type": "month_end_closing",
        "known_misclassification": True,
        "production_type": "UNKNOWN",
        "file_count": 0,
    },
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _classify_local(prompt: str) -> str:
    """Classify using the rule-based classifier in main.py."""
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from main import _classify_rule_based
        result = asyncio.get_event_loop().run_until_complete(_classify_rule_based(prompt))
        if hasattr(result, "task_type"):
            val = result.task_type
            # Handle TaskType enum: TaskType.CREATE_EMPLOYEE → create_employee
            return val.value.lower() if hasattr(val, "value") else str(val).split(".")[-1].lower()
        return str(result).lower()
    except ImportError:
        # Fallback: use classifier.py keyword path
        from classifier import _keyword_fallback
        result = _keyword_fallback(prompt)
        if result:
            return result.task_type.value.lower()
        return "unknown"


def run_smoke_tests(verbose: bool = False) -> None:
    """Run all smoke test cases and report results."""
    print(f"{'='*70}")
    print(f"GOLDEN SMOKE TEST — 19 real grader prompts (2026-03-21)")
    print(f"{'='*70}\n")

    passed = 0
    failed = 0
    misclass_fixed = 0
    misclass_still_broken = 0
    results = []

    for case in SMOKE_CASES:
        cid = case["id"]
        lang = case["lang"]
        expected = case["expected_type"].lower()
        prompt = case["prompt"]
        is_known_misclass = case.get("known_misclassification", False)
        prod_type = case.get("production_type", "")

        try:
            got = _classify_local(prompt).lower()
            # Normalize enum value
            got = got.replace("tasktype.", "").strip()
        except Exception as e:
            got = f"ERROR: {e}"

        match = (got == expected)
        status = "PASS" if match else "FAIL"

        if is_known_misclass:
            if match:
                status = "FIXED"
                misclass_fixed += 1
            else:
                status = "STILL_BROKEN"
                misclass_still_broken += 1
        elif match:
            passed += 1
        else:
            failed += 1

        tag = f"[{status}]"
        if is_known_misclass:
            tag += f" (was {prod_type})"

        print(f"  {cid:2d}. {tag:30s} {lang:3s}  expected={expected:30s}  got={got}")

        if verbose:
            print(f"      prompt: {prompt[:90]}...")

        results.append({
            "id": cid,
            "lang": lang,
            "expected": expected,
            "got": got,
            "match": match,
            "known_misclassification": is_known_misclass,
        })

    # Summary
    total = len(SMOKE_CASES)
    normal_total = total - (misclass_fixed + misclass_still_broken)
    known_total = misclass_fixed + misclass_still_broken

    print(f"\n{'='*70}")
    print(f"RESULTS: {passed}/{normal_total} normal passed, {failed} failed")
    print(f"KNOWN MISCLASSIFICATIONS: {misclass_fixed}/{known_total} fixed, {misclass_still_broken} still broken")
    print(f"OVERALL: {passed + misclass_fixed}/{total} correct ({100*(passed+misclass_fixed)/total:.0f}%)")
    print(f"{'='*70}")


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    run_smoke_tests(verbose=verbose)
