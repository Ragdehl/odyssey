import aws_cdk as cdk
from aws_cdk import Environment
from cdk_project.odyssey_cfg import get_cfg
from cdk_project.stacks.pipeline_stack import PipelineStack

app = cdk.App()
cfg = get_cfg(app)

PIPELINE_ENV = Environment(account=cfg.env.account_id, region=cfg.env.region)
APP_ENV      = PIPELINE_ENV

PipelineStack(
    app,
    "OdysseyPipelineStack",
    env=PIPELINE_ENV,
    github_owner=cfg.github.owner,
    github_repo=cfg.github.repo,
    connection_arn=cfg.env.resolved_connection_arn,
    env_name=cfg.env.name,
    branch=cfg.env.branch,
    app_env=APP_ENV,
)

app.synth()
