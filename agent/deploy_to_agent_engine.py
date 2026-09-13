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
import vertexai
from demo_2lo_agent.agent import agent
from vertexai import types
from vertexai.agent_engines import AdkApp

# Initialize the Vertex AI client with v1beta1 API for Agent Identity support
client = vertexai.Client(
    # project="cs-peter-lam-cds3487",
    project="project-6a0884c5-1380-4d43-808",
    location="us-central1",
    http_options=dict(api_version="v1beta1")
)

# Use the proper wrapper class for your Agent Framework (e.g., AdkApp)
app = AdkApp(agent=agent)

# Deploy the agent with Agent Identity enabled
remote_app = client.agent_engines.create(
    agent=app,
    config={
        # "staging_bucket": "gs://peter_lam_gcs",
        "staging_bucket": "gs://peterlam_gcs",
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        "requirements": [
            "google-cloud-aiplatform[agent_engines,adk]",
            "google-adk[agent-identity,mcp]>=2.7.1",
            "pydantic==2.13.5",
            "cloudpickle==3.1.2"
        ],
        "extra_packages": ["demo_2lo_agent"]
    }
)

print("Deployed:", agent.resource_name)
print(
    "\nNow grant the agent's identity access to the auth provider, e.g.:\n"
    "  gcloud alpha agent-identity authProviders add-iam-policy-binding "
    "AUTH_PROVIDER_NAME \\\n"
    "    --location=LOCATION \\\n"
    "    --role=roles/iamconnectors.user \\\n"
    "    --member='<agent identity principal for this engine>'\n"
    "\nSee the 2LO docs for the exact principal format for your engine."
)

#gcloud alpha agent-identity auth-provders add-iam-policy-binding mock-2lo-auth-provider --location=us-central1 --role=roles/agentidentity.user --member='principal://...'
# gcloud alpha agent-identity auth-providers add-iam-policy-binding mock-2lo-oauth-auth-provider-2 --location=us-central1 --role=roles/agentidentity.user --member='principal://agents.global.org-57132782248.system.id.goog/resources/aiplatform/projects/869928330868/locations/us-central1/reasoningEngines/5094536000009404416'
