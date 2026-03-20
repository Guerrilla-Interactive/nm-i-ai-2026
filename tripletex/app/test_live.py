import httpx
import asyncio
import json
import sys

ENDPOINT = "https://coralie-overaffected-mazie.ngrok-free.dev"
CREDS = {
    "base_url": "https://kkpqfuj-amager.tripletex.dev/v2",
    "session_token": "eyJ0b2tlbklkIjoyMTQ3NjUyNjMyLCJ0b2tlbiI6ImQ4NWU3MDZmLWI1MjQtNDk0MS04ZTQ1LWUxZWNiMjVlN2M2MyJ9"
}

# Test ALL task types across multiple languages
TESTS = [
    # Tier 1 — Norwegian
    ("T1-nb-dept", "Opprett en avdeling med navn Logistikk og avdelingsnummer 60"),
    ("T1-nb-cust", "Opprett en kunde med navn Fjord Shipping AS"),
    ("T1-nb-emp", "Opprett en ansatt med fornavn Lars og etternavn Berg, e-post lars@fjord.no"),
    ("T1-nb-prod", "Opprett et produkt med navn Frakttjeneste til 2500 kr"),
    ("T1-nb-proj", "Opprett et prosjekt med navn Havnelogistikk"),

    # Tier 1 — English
    ("T1-en-dept", "Create a department called Research with number 70"),
    ("T1-en-cust", "Create a customer named Nordic Solutions AB with email info@nordic.se"),
    ("T1-en-emp", "Create an employee named Emma Wilson with email emma@nordic.se"),
    ("T1-en-prod", "Create a product called API Integration Service priced at 3500 NOK"),

    # Tier 1 — German
    ("T1-de-cust", "Erstellen Sie einen Kunden namens München GmbH"),
    ("T1-de-dept", "Erstellen Sie eine Abteilung namens Vertrieb mit Nummer 80"),

    # Tier 1 — French
    ("T1-fr-dept", "Créer un département appelé Finance avec numéro 90"),
    ("T1-fr-cust", "Créer un client appelé Paris Conseil SAS"),

    # Tier 1 — Spanish
    ("T1-es-cust", "Crear un cliente llamado Barcelona Tech SL"),

    # Tier 2 — Invoice (most valuable)
    ("T2-nb-inv", "Opprett en faktura for kunde Fjord Shipping AS med 3 timer Frakttjeneste til 2500 kr per stk"),
    ("T2-en-inv", "Create an invoice for customer Nordic Solutions AB for 5 units of API Integration Service at 3500 NOK each"),

    # Tier 2 — Travel expense
    ("T2-nb-travel", "Registrer en reiseregning med tittel Kundebesøk Bergen"),

    # Tier 2 — Contact
    ("T2-nb-contact", "Opprett en kontaktperson Per Olsen for kunde Fjord Shipping AS med e-post per@fjord.no"),
]

async def run_tests():
    results = []
    async with httpx.AsyncClient(timeout=120) as client:
        for test_id, prompt in TESTS:
            body = {"prompt": prompt, "files": [], "tripletex_credentials": CREDS}
            try:
                resp = await client.post(f"{ENDPOINT}/solve", json=body)
                status = "PASS" if resp.status_code == 200 else f"FAIL HTTP {resp.status_code}"
                results.append((test_id, status, resp.status_code, resp.text[:200]))
                icon = "✅" if resp.status_code == 200 else "❌"
                print(f"{icon} {test_id:20s} | HTTP {resp.status_code} | {resp.text[:100]}")
            except Exception as e:
                results.append((test_id, f"ERROR: {e}", 0, str(e)[:200]))
                print(f"❌ {test_id:20s} | ERROR: {e}")
            await asyncio.sleep(0.5)  # Don't hammer the endpoint

    return results

results = asyncio.run(run_tests())

# Summary
passed = sum(1 for _, s, _, _ in results if s == "PASS")
total = len(results)
print(f"\n{'='*60}")
print(f"RESULTS: {passed}/{total} passed")
print(f"{'='*60}")
