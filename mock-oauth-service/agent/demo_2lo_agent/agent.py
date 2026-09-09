"""
ADK agent demonstrating 2-legged OAuth (2LO) via GCP Agent Identity
auth manager, against a mock OAuth server + dummy orders API hosted on
Cloud Run (see ../mock-oauth-service).

Flow:
  1. GcpAuthProvider is registered with the CredentialManager (done once).
  2. The tool is wrapped in AuthenticatedFunctionTool with an AuthConfig
     whose scheme points at the 2LO auth provider resource.
  3. At tool-invocation time, ADK asks the auth manager for a token; the
     auth manager performs the client_credentials exchange against the
     Cloud Run /token endpoint using the client id/secret it vaults, and
     the resulting access token is injected into the tool call.
  4. The tool calls the protected /api/orders endpoint with the token.

Pattern follows the official ADK sample:
  https://github.com/google/adk-python/tree/main/contributing/samples/integrations/gcp_auth
"""

import os

import httpx
from google.adk.agents.llm_agent import LlmAgent
from google.adk.auth.auth_credential import AuthCredential
from google.adk.auth.auth_tool import AuthConfig
from google.adk.auth.credential_manager import CredentialManager
from google.adk.integrations.agent_identity import (
    GcpAuthProvider,
    GcpAuthProviderScheme,
)
from google.adk.tools.authenticated_function_tool import AuthenticatedFunctionTool

# ---------------------------------------------------------------------------
# Configuration (set these in agent/.env or your shell)
# ---------------------------------------------------------------------------
# Full resource name of the 2LO auth provider created by
# scripts/2_create_auth_provider.sh, e.g.:
#   projects/my-proj/locations/us-central1/authProviders/mock-orders-2lo
# (older Connectors API surface: .../connectors/mock-orders-2lo)
ORDERS_2LO_AUTH_PROVIDER = os.environ["ORDERS_2LO_AUTH_PROVIDER"]

# Base URL of the Cloud Run mock service, e.g.:
#   https://mock-2lo-oauth-XXXX-uc.a.run.app
ORDERS_API_BASE_URL = os.environ["ORDERS_API_BASE_URL"].rstrip("/")

# ---------------------------------------------------------------------------
# 1) Register the Agent Identity auth provider (once per process).
# ---------------------------------------------------------------------------
CredentialManager.register_auth_provider(GcpAuthProvider())

# ---------------------------------------------------------------------------
# 2) Auth config pointing at the 2LO auth provider resource.
# ---------------------------------------------------------------------------
orders_auth_config = AuthConfig(
    auth_scheme=GcpAuthProviderScheme(name=ORDERS_2LO_AUTH_PROVIDER)
)


# ---------------------------------------------------------------------------
# 3) Tool functions. ADK injects the resolved credential as the
#    `credential` argument at invocation time.
# ---------------------------------------------------------------------------
def _bearer_headers(credential: AuthCredential) -> dict:
    """Extract the access token from the injected AuthCredential."""
    token = None
    if credential and credential.oauth2:
        token = credential.oauth2.access_token
    if not token and credential and getattr(credential, "http", None):
        # Some provider versions surface the token as an HTTP bearer credential.
        token = credential.http.credentials.token
    if not token:
        raise RuntimeError(
            "No access token was injected. Check that the auth provider "
            "resource name is correct and your identity has "
            "roles/iamconnectors.user on it."
        )
    return {"Authorization": f"Bearer {token}"}


def list_orders(credential: AuthCredential) -> dict:
    """Lists all customer orders from the orders system.

    Returns:
        A dict containing the list of orders with id, customer, total,
        and status for each.
    """
    resp = httpx.get(
        f"{ORDERS_API_BASE_URL}/api/orders",
        headers=_bearer_headers(credential),
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def get_order(order_id: str, credential: AuthCredential) -> dict:
    """Gets details for a single order by its order id.

    Args:
        order_id: The order id, for example "ORD-1001".

    Returns:
        A dict with the order's customer, total, and status.
    """
    resp = httpx.get(
        f"{ORDERS_API_BASE_URL}/api/orders/{order_id}",
        headers=_bearer_headers(credential),
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


list_orders_tool = AuthenticatedFunctionTool(
    func=list_orders,
    auth_config=orders_auth_config,
)

get_order_tool = AuthenticatedFunctionTool(
    func=get_order,
    auth_config=orders_auth_config,
)

# ---------------------------------------------------------------------------
# 4) The agent.
# ---------------------------------------------------------------------------
root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="orders_2lo_demo_agent",
    instruction=(
        "You are an assistant for the ACME orders system. "
        "Use the list_orders tool to see all orders and the get_order tool "
        "to look up a specific order by id. Authentication to the orders "
        "API is handled for you automatically via 2-legged OAuth - never "
        "ask the user for credentials."
    ),
    tools=[list_orders_tool, get_order_tool],
)
