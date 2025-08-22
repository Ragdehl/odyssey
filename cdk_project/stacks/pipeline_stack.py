from aws_cdk import (
    Stack,
    Stage,
    pipelines as pipelines,
    Environment,
    aws_iam as iam,
)
from constructs import Construct
from cdk_project.stacks.site_stack import StaticSiteStack
from cdk_project.stacks.chat_backend_stack import ChatBackendStack
from cdk_project.builders.policy_builder import apply_policies_to_role

class AppStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, env_name: str, app_env: Environment, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        StaticSiteStack(self, f"StaticSiteStack-{env_name}", env_name=env_name, env=app_env)
        ChatBackendStack(self, f"ChatBackendStack-{env_name}", env_name=env_name, env=app_env)

class OdysseyPipelineStack(Stack):
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
        manual_approval: bool = False, # true en prod
        app_env: Environment | None = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        source = pipelines.CodePipelineSource.connection(
            f"{github_owner}/{github_repo}",
            branch,
            connection_arn=connection_arn,
        )

        synth = pipelines.ShellStep(
            "Synth",
            input=source,
            commands=[
                "pip install -r requirements.txt",
                "npm i -g aws-cdk",
                f"cdk synth -c odyssey.env={env_name}",
            ]
        )

        pipeline = pipelines.CodePipeline(
            self, 
            "Odyssey-Static-Site-Pipeline",
            pipeline_name="Odyssey-Static-Site-Pipeline",
            synth=synth
        )

        stage = AppStage(self, env_name.capitalize(), env_name=env_name, app_env=app_env)

        if manual_approval:
            pipeline.add_stage(stage, pre=[pipelines.ManualApprovalStep("ApproveDeployment")])
        else:
            pipeline.add_stage(stage)

        pipeline.build_pipeline()

        apply_policies_to_role(
            pipeline.pipeline.role,
            "pipeline.json",
            base_dir="cdk_project/configs/iam/policies",
        )