#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/app"

# ── Config ──
SERVICE_NAME="tripletex-agent"
REGION="europe-north1"
PROJECT_ID="${GCP_PROJECT:?Set GCP_PROJECT env var}"

echo ">>> Deploying $SERVICE_NAME to $REGION (project: $PROJECT_ID)..."

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 300 \
  --min-instances 1 \
  --max-instances 5 \
  --concurrency 1 \
  --set-env-vars "GEMINI_MODEL=gemini-2.5-pro,GOOGLE_API_KEY=AIzaSyBvI-STjacToDLIbFslvuVcI1Z3QVAWGrc"

URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format='value(status.url)')

echo ""
echo ">>> Deployed to: $URL"
echo ">>> Register this URL at https://app.ainm.no"
echo ">>> Test: curl -X POST $URL/solve -H 'Content-Type: application/json' -d '{\"prompt\":\"test\",\"tripletex_credentials\":{\"base_url\":\"https://tx-proxy.ainm.no/v2\",\"session_token\":\"test\"}}'"
