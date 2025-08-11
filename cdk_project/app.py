import os
import aws_cdk as cdk
from aws_cdk import Environment
from cdk_project.pipeline_stack import PipelineStack

app = cdk.App()

# === Variables de entorno requeridas ===
# ODYSSEY_ENV: "dev" | "main"
ENV_NAME = os.getenv("ODYSSEY_ENV", "dev").lower()  # por defecto "dev"

# Puedes personalizar qué rama corresponde a cada entorno
DEV_BRANCH = os.getenv("ODYSSEY_DEV_BRANCH", "dev")
MAIN_BRANCH = os.getenv("ODYSSEY_MAIN_BRANCH", "main")
BRANCH = DEV_BRANCH if ENV_NAME == "dev" else MAIN_BRANCH

GITHUB_OWNER = os.getenv("ODYSSEY_GH_OWNER", "TU_USUARIO_GITHUB")
GITHUB_REPO  = os.getenv("ODYSSEY_GH_REPO", "TU_REPO")
CONNECTION_ARN = os.getenv("ODYSSEY_CONNECTION_ARN", "arn:aws:codestar-connections:REGION:ACCOUNT_ID:connection/ID")

ACCOUNT_ID = os.getenv("CDK_DEFAULT_ACCOUNT") or "ACCOUNT_ID"
REGION     = os.getenv("CDK_DEFAULT_REGION")  or "eu-west-1"  # elige tu región

PIPELINE_ENV = Environment(account=ACCOUNT_ID, region=REGION)  # dónde vive el pipeline
APP_ENV      = Environment(account=ACCOUNT_ID, region=REGION)  # dónde despliegas la app

PipelineStack(
    app, "OdysseyPipelineStack",
    env=PIPELINE_ENV,
    github_owner=GITHUB_OWNER,
    github_repo=GITHUB_REPO,
    connection_arn=CONNECTION_ARN,
    env_name=ENV_NAME,
    branch=BRANCH,
    app_env=APP_ENV,
)

app.synth()