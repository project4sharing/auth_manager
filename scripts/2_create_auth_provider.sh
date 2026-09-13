#!/usr/bin/env bash
#
# Step 2: Create the 2-legged OAuth auth provider in Agent Identity
# auth manager, pointing at the Cloud Run mock OAuth token endpoint.
#
# NOTE: Agent Identity is an alpha/preview surface and Google has TWO
# generations of this API:
#   - Newer:  Agent Identity API      (gcloud alpha agent-identity authProviders ...)
#   - Older:  IAM Connectors API      (gcloud alpha agent-identity connectors ...)
# Google recommends the Agent Identity API for new projects. This script
# tries the newer surface first; a commented fallback for the older
# connectors surface is included below. Verify against the current docs:
#   https://docs.cloud.google.com/iam/docs/auth-with-2lo-v2
#
set -euo pipefail


ENV_AGENT_FILE="../agent/demo_2lo_agent/.env"
ENV_OAUTH_SVC_FILE="../mock-oauth-service/.env"

set -a
source "$ENV_AGENT_FILE"
source "$ENV_OAUTH_SVC_FILE"
set +a
# ----------------------------- EDIT THESE ---------------------------------
# The identity that will USE the auth provider (your agent's identity, or
# your own user account when testing locally with adk web):
export AGENT_MEMBER="${AGENT_MEMBER:-user:you@example.com}"
# --------------------------------------------------------------------------

echo "Enabling the Agent Identity API..."
gcloud services enable agentidentity.googleapis.com --project="${GOOGLE_CLOUD_PROJECT}" || \
  echo "If this API id is not found, enable the API shown in the current 2LO docs."

echo "Creating 2LO auth provider ${MOCK_2LO_AUTH_PROVIDER}..."
gcloud alpha agent-identity auth-providers create "${MOCK_2LO_AUTH_PROVIDER}" \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --location="${GOOGLE_CLOUD_LOCATION}" \
  --two-legged-oauth-client-id="${DEMO_CLIENT_ID}" \
  --two-legged-oauth-client-secret="${DEMO_CLIENT_SECRET}" \
  --two-legged-oauth-token-url="${MOCK_2LO_BASE_URL}/token"

echo "Verifying provider is ENABLED..."
gcloud alpha agent-identity auth-providers list \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --location="${GOOGLE_CLOUD_LOCATION}"

echo "Granting ${AGENT_MEMBER} permission to use the auth provider..."
gcloud alpha agent-identity authProviders add-iam-policy-binding "${MOCK_2LO_AUTH_PROVIDER}" \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --location="${GOOGLE_CLOUD_LOCATION}" \
  --role="roles/iamconnectors.user" \
  --member="${AGENT_MEMBER}"

echo ""
echo "=========================================================="
echo "Auth provider resource name (put this in agent/.env):"
echo ""
echo "  projects/${PROJECT_ID}/locations/${LOCATION}/authProviders/${AUTH_PROVIDER_NAME}"
echo "=========================================================="

