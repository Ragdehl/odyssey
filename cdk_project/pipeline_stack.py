from aws_cdk import (
    Stack,
    Stage,
    pipelines as pipelines,
    Environment,
)
from constructs import Construct
from .app_stack import StaticSiteStack

# A Stage is a collection of stacks that are deployed together.
class AppStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        StaticSiteStack(self, f"StaticSiteStack-{env_name}", env_name=env_name)


class PipelineStack(Stack):
    """
    This stack creates the CodePipeline that automates the deployment
    of your S3 website to 'dev' and 'main' environments.
    """
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        github_owner: str,
        github_repo: str,
        connection_arn: str,
        env_name: str,                 # "dev" | "main"
        branch: str,                   # p.ej. "dev" o "main"
        app_env: Environment | None = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        source = pipelines.CodePipelineSource.connection(
            f"{github_owner}/{github_repo}",
            branch,
            connection_arn=connection_arn,
        )

        pipeline = pipelines.CodePipeline(
            self, "Odyssey-Static-Site-Pipeline",
            pipeline_name="Odyssey-Static-Site-Pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=source,
                commands=[
                    "pip install -r requirements.txt",
                    "npm install -g aws-cdk",
                    "cdk synth"
                ]
            )
        )

        stage = AppStage(
            self, env_name.capitalize(),
            env_name=env_name,
            env=app_env,
        )

        if env_name.lower() == "main":
            pipeline.add_stage(stage, pre=[pipelines.ManualApprovalStep("ApproveMainDeployment")])
        else:
            pipeline.add_stage(stage)