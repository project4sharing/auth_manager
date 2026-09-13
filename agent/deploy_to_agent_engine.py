"""
Optional Step 4: Deploy the agent to Vertex AI Agent Engine.

Deploying to Agent Engine gives the agent its own Agent Identity, which is
the more faithful end-to-end demo: grant roles/iamconnectors.user to the
agent's identity instead of your user account.

Usage:
    pip install "google-cloud-aiplatform[adk,agent_engines]"
    python deploy_to_agent_engine.py
"""
from pathlib import Path
from dotenv import load_dotenv
import os

import vertexai
from vertexai import types
from vertexai.agent_engines import AdkApp

env_path = Path(__file__).parent.parent / "agent" / "demo_2lo_agent" / ".env"
print(f"#####  Loading environment variables from {env_path}")
if not load_dotenv(dotenv_path=env_path):
    raise FileNotFoundError(f"Could not load dotenv file: {env_path}")

from demo_2lo_agent.agent import agent

GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "NULL_GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "NULL_GOOGLE_CLOUD_LOCATION")
STAGING_GCP_PROJECT = os.environ.get("STAGING_GCP_PROJECT", "NULL_STAGING_GCP_PROJECT")

print(f"#####  GOOGLE_CLOUD_PROJECT:: {GOOGLE_CLOUD_PROJECT}")
print(f"#####  GOOGLE_CLOUD_LOCATION:: {GOOGLE_CLOUD_LOCATION}")
print(f"#####  STAGING_GCP_PROJECT:: {STAGING_GCP_PROJECT}")

# Initialize the Vertex AI client with v1beta1 API for Agent Identity support
client = vertexai.Client(
    project=GOOGLE_CLOUD_PROJECT,
    location=GOOGLE_CLOUD_LOCATION,
    http_options=dict(api_version="v1beta1")
)

# Use the proper wrapper class for your Agent Framework (e.g., AdkApp)
app = AdkApp(agent=agent)

# Deploy the agent with Agent Identity enabled
remote_app = client.agent_engines.create(
    agent=app,
    config={
        "display_name": "mock-auth-manager-agent",
        "staging_bucket": STAGING_GCP_PROJECT,
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        "requirements": [
            "google-cloud-aiplatform[agent_engines,adk]",
            "google-adk[agent-identity,mcp]>=2.7.1",
            "pydantic==2.13.5",
            "cloudpickle==3.1.2"
        ],
        "extra_packages": ["demo_2lo_agent"],
        "env_vars": {
            "MOCK_2LO_BASE_URL": os.environ.get("MOCK_2LO_BASE_URL", "NULL_MOCK_2LO_BASE_URL"),
            "MOCK_2LO_AUTH_PROVIDER": os.environ.get("MOCK_2LO_AUTH_PROVIDER", "NULL_MOCK_2LO_AUTH_PROVIDER"),
            "FULL_MOCK_2LO_AUTH_PROVIDER": f"projects/{os.environ.get('GOOGLE_CLOUD_PROJECT')}/locations/{os.environ.get('GOOGLE_CLOUD_LOCATION')}/authProviders/{os.environ.get('MOCK_2LO_AUTH_PROVIDER')}",
            "ORDERS_API_BASE_URL": f"projects/{os.environ.get('GOOGLE_CLOUD_PROJECT')}/locations/{os.environ.get('GOOGLE_CLOUD_LOCATION')}/authProviders/{os.environ.get('MOCK_2LO_AUTH_PROVIDER')}"
        }
    }
)


# gcloud alpha agent-identity auth-providers add-iam-policy-binding mock-2lo-auth-provider --location=us-central1 --role=roles/agentidentity.user --member='principal://...'