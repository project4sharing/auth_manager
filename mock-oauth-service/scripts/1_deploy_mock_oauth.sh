#!/usr/bin/env bash
#
# Step 1: Deploy the mock OAuth server + dummy API to Cloud Run.
#
# The resulting *.run.app URL is hosted on Google infrastructure, so the
# Agent Identity auth manager and Agent Engine can reach it without any
# egress to the public internet from your VPC.
#
set -euo pipefail

# ----------------------------- EDIT THESE ---------------------------------
export PROJECT_ID="${PROJECT_ID:-your-project-id}"
export REGION="${REGION:-us-central1}"
export SERVICE_NAME="${SERVICE_NAME:-mock-2lo-oauth}"

# Demo OAuth client credentials. These are what you will later store in the
# 2LO auth provider. For a real demo, generate random values:
export DEMO_CLIENT_ID="${DEMO_CLIENT_ID:-demo-client}"
export DEMO_CLIENT_SECRET="${DEMO_CLIENT_SECRET:-$(openssl rand -hex 16)}"
export TOKEN_SIGNING_KEY="${TOKEN_SIGNING_KEY:-$(openssl rand -hex 32)}"
# --------------------------------------------------------------------------

echo "Deploying ${SERVICE_NAME} to Cloud Run in ${PROJECT_ID}/${REGION}..."

gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --source="$(dirname "$0")/../mock-oauth-service" \
  --allow-unauthenticated \
  --set-env-vars="DEMO_CLIENT_ID=${DEMO_CLIENT_ID},DEMO_CLIENT_SECRET=${DEMO_CLIENT_SECRET},TOKEN_SIGNING_KEY=${TOKEN_SIGNING_KEY}"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --format='value(status.url)')

echo ""
echo "=========================================================="
echo "Mock OAuth service deployed."
echo ""
echo "  Service URL:    ${SERVICE_URL}"
echo "  Token endpoint: ${SERVICE_URL}/token"
echo "  Resource API:   ${SERVICE_URL}/api/orders"
echo "  Client ID:      ${DEMO_CLIENT_ID}"
echo "  Client secret:  ${DEMO_CLIENT_SECRET}"
echo ""
echo "Smoke test (run these now to verify before wiring up the agent):"
echo ""
echo "  # 1) Get a token"
echo "  curl -s -X POST ${SERVICE_URL}/token \\"
echo "    -d grant_type=client_credentials \\"
echo "    -d client_id=${DEMO_CLIENT_ID} \\"
echo "    -d client_secret=${DEMO_CLIENT_SECRET}"
echo ""
echo "  # 2) Call the protected API with the returned access_token"
echo "  curl -s ${SERVICE_URL}/api/orders -H 'Authorization: Bearer <ACCESS_TOKEN>'"
echo ""
echo "  # 3) Confirm it rejects unauthenticated calls (expect 401)"
echo "  curl -s -o /dev/null -w '%{http_code}\n' ${SERVICE_URL}/api/orders"
echo "=========================================================="
