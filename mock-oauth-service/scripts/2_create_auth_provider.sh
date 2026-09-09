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

# ----------------------------- EDIT THESE ---------------------------------
export PROJECT_ID="${PROJECT_ID:-your-project-id}"
export LOCATION="${LOCATION:-us-central1}"
export AUTH_PROVIDER_NAME="${AUTH_PROVIDER_NAME:-mock-orders-2lo}"

# From the output of 1_deploy_mock_oauth.sh:
export TOKEN_ENDPOINT="${TOKEN_ENDPOINT:-https://mock-2lo-oauth-XXXX-uc.a.run.app/token}"
export DEMO_CLIENT_ID="${DEMO_CLIENT_ID:-demo-client}"
export DEMO_CLIENT_SECRET="${DEMO_CLIENT_SECRET:-demo-secret}"

# The identity that will USE the auth provider (your agent's identity, or
# your own user account when testing locally with adk web):
export AGENT_MEMBER="${AGENT_MEMBER:-user:you@example.com}"
# --------------------------------------------------------------------------

echo "Enabling the Agent Identity API..."
gcloud services enable agentidentity.googleapis.com --project="${PROJECT_ID}" || \
  echo "If this API id is not found, enable the API shown in the current 2LO docs."

echo "Creating 2LO auth provider ${AUTH_PROVIDER_NAME}..."
gcloud alpha agent-identity authProviders create "${AUTH_PROVIDER_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${LOCATION}" \
  --two-legged-oauth-client-id="${DEMO_CLIENT_ID}" \
  --two-legged-oauth-client-secret="${DEMO_CLIENT_SECRET}" \
  --two-legged-oauth-token-endpoint="${TOKEN_ENDPOINT}"

echo "Verifying provider is ENABLED..."
gcloud alpha agent-identity authProviders list \
  --project="${PROJECT_ID}" \
  --location="${LOCATION}"

echo "Granting ${AGENT_MEMBER} permission to use the auth provider..."
gcloud alpha agent-identity authProviders add-iam-policy-binding "${AUTH_PROVIDER_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${LOCATION}" \
  --role="roles/iamconnectors.user" \
  --member="${AGENT_MEMBER}"

echo ""
echo "=========================================================="
echo "Auth provider resource name (put this in agent/.env):"
echo ""
echo "  projects/${PROJECT_ID}/locations/${LOCATION}/authProviders/${AUTH_PROVIDER_NAME}"
echo "=========================================================="

# --------------------------------------------------------------------------
# FALLBACK: older IAM Connectors API surface (auth-with-2lo, not -v2).
# Uncomment if the authProviders commands are unavailable in your gcloud.
# The resource name format then becomes .../connectors/NAME instead.
# --------------------------------------------------------------------------
# gcloud services enable iamconnectors.googleapis.com --project="${PROJECT_ID}"
#
# gcloud alpha agent-identity connectors create "${AUTH_PROVIDER_NAME}" \
#   --project="${PROJECT_ID}" \
#   --location="${LOCATION}" \
#   --two-legged-oauth-client-id="${DEMO_CLIENT_ID}" \
#   --two-legged-oauth-client-secret="${DEMO_CLIENT_SECRET}" \
#   --two-legged-oauth-token-endpoint="${TOKEN_ENDPOINT}"
#
# gcloud alpha agent-identity connectors add-iam-policy-binding "${AUTH_PROVIDER_NAME}" \
#   --project="${PROJECT_ID}" \
#   --location="${LOCATION}" \
#   --role="roles/iamconnectors.user" \
#   --member="${AGENT_MEMBER}"
#
# Resource name: projects/${PROJECT_ID}/locations/${LOCATION}/connectors/${AUTH_PROVIDER_NAME}
