"""
Optional Step 4: Deploy the agent to Vertex AI Agent Engine.

For a quick demo you do NOT need this - `adk web` running locally (or on a
Workbench/Cloud Shell instance) is enough, as long as YOUR user identity has
roles/iamconnectors.user on the auth provider.

Deploying to Agent Engine gives the agent its own Agent Identity, which is
the more faithful end-to-end demo: grant roles/iamconnectors.user to the
agent's identity instead of your user account.

Usage:
    pip install "google-cloud-aiplatform[adk,agent_engines]"
    python deploy_to_agent_engine.py
"""

import os

import vertexai
from vertexai import agent_engines

from demo_2lo_agent.agent import root_agent

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.environ["STAGING_BUCKET"]  # e.g. gs://my-agent-staging

vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

app = agent_engines.AdkApp(agent=root_agent, enable_tracing=True)

remote_agent = agent_engines.create(
    app,
    display_name="orders-2lo-demo-agent",
    requirements=[
        "google-adk>=1.0.0",
        "google-cloud-aiplatform[adk,agent_engines]",
        "httpx>=0.27.0",
    ],
    env_vars={
        "ORDERS_2LO_AUTH_PROVIDER": os.environ["ORDERS_2LO_AUTH_PROVIDER"],
        "ORDERS_API_BASE_URL": os.environ["ORDERS_API_BASE_URL"],
    },
)

print("Deployed:", remote_agent.resource_name)
print(
    "\nNow grant the agent's identity access to the auth provider, e.g.:\n"
    "  gcloud alpha agent-identity authProviders add-iam-policy-binding "
    "AUTH_PROVIDER_NAME \\\n"
    "    --location=LOCATION \\\n"
    "    --role=roles/iamconnectors.user \\\n"
    "    --member='<agent identity principal for this engine>'\n"
    "\nSee the 2LO docs for the exact principal format for your engine."
)
