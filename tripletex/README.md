# Tripletex — AI Accounting Agent

## Overview
Build an HTTPS endpoint (`POST /solve`) that receives accounting tasks and completes them via the Tripletex API.

## API
- Base: `https://kkpqfuj-amager.tripletex.dev/v2`
- Auth: Basic Auth (username: 0, password: session token)
- Endpoints: employees, customers, products, invoices, projects, departments, travel expenses

## Scoring
- Field-by-field correctness
- Tier multiplier: T1 ×1.0, T2 ×2.0, T3 ×3.0
- Efficiency bonus: up to 2× for minimal API calls
- Score range: 0.0 – 6.0

## Task Categories
- Employee management (create, roles, contact)
- Customer/product registration
- Invoicing and payments
- Travel expense reports
- Project creation
- Error corrections/reversals
- Department setup, module enablement
