#!/usr/bin/env bash
#
# Step 1: Deploy the mock OAuth server + dummy API to Cloud Run function (gen2).
#
#
set -euo pipefail

# ----------------------------- EDIT THESE ---------------------------------
ENV_AGENT_FILE="../agent/demo_2lo_agent/.env"
ENV_OAUTH_SVC_FILE="../mock-oauth-service/.env"

set -a
source "$ENV_AGENT_FILE"
source "$ENV_OAUTH_SVC_FILE"
set +a
# --------------------------------------------------------------------------


# gcloud services enable cloudfunctions.googleapis.com run.googleapis.com \
    cloudbuild.googleapis.com --project="${PROJECT_ID}"

echo "Deploying ${SERVICE_NAME} Cloud run function in ${PROJECT_ID}/${REGION}..."

gcloud functions deploy "mock-oauth-service" --project="${PROJECT_ID}" --region="${REGION}" --gen2 --runtime=python312 --source="../mock-oauth-service" --entry-point=app --trigger-http --allow-unauthenticated --set-env-vars="DEMO_CLIENT_ID=${DEMO_CLIENT_ID},DEMO_CLIENT_SECRET=${DEMO_CLIENT_SECRET},TOKEN_SIGNING_KEY=${TOKEN_SIGNING_KEY}"

FUNCTION_URL=$(gcloud functions describe "${FUNCTION_NAME}" \
  --project="${PROJECT_ID}" --region="${REGION}" --gen2 \
  --format='value(serviceConfig.uri)')

echo ""
echo "=========================================================="
echo "Function deployed."
echo ""
echo "  Base URL:       ${FUNCTION_URL}"
echo "  Token endpoint: ${FUNCTION_URL}/token      <- use in auth provider"
echo "  Resource API:   ${FUNCTION_URL}/api/orders <- use as ORDERS_API_BASE_URL base"
echo "  Client ID:      ${DEMO_CLIENT_ID}"
echo "  Client secret:  ${DEMO_CLIENT_SECRET}"
echo ""
echo "Smoke test:"
echo "  python3 $(dirname "$0")/smoke_test.py ${FUNCTION_URL} ${DEMO_CLIENT_ID} ${DEMO_CLIENT_SECRET}"
echo ""
echo "In agent/.env set:"
echo "  ORDERS_API_BASE_URL=${FUNCTION_URL}"
echo "=========================================================="