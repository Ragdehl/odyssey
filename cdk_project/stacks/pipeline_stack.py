"""
CI/CD pipeline stack for Odyssey CDK project.

This stack creates a CodePipeline for automated deployment of the Odyssey application.
It includes source code integration with GitHub, build steps, and deployment stages
with optional manual approval for production environments.
"""

from __future__ import annotations

from aws_cdk import (
    Environment,
    Stack,
    Stage,
)
from aws_cdk import (
    pipelines as pipelines,
)
from constructs import Construct

from cdk_project.builders.policy_builder import apply_policies_to_role
from cdk_project.stacks.chat_backend_stack import ChatBackendStack
from cdk_project.stacks.site_stack import StaticSiteStack


class AppStage(Stage):
    """
    Application stage containing all stacks for a specific environment.

    This stage deploys both the static site and chat backend stacks
    for the specified environment.
    """

    def __init__(
        self, scope: Construct, construct_id: str, env_name: str, app_env: Environment, **kwargs
    ) -> None:
        """
        Initialize the application stage.

        Args:
            scope: CDK construct scope
            construct_id: Construct ID
            env_name: Environment name
            app_env: AWS environment configuration
            **kwargs: Additional stage properties
        """
        super().__init__(scope, construct_id, **kwargs)
        StaticSiteStack(self, f"StaticSiteStack-{env_name}", env_name=env_name, env=app_env)
        ChatBackendStack(self, f"ChatBackendStack-{env_name}", env_name=env_name, env=app_env)


class OdysseyPipelineStack(Stack):
    """
    Main pipeline stack for Odyssey application deployment.

    Creates a CodePipeline that automatically builds and deploys
    the Odyssey application from GitHub source code.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        github_owner: str,
        github_repo: str,
        connection_arn: str,
        env_name: str,  # "dev" | "main"
        branch: str,  # e.g. "dev" or "main"
        manual_approval: bool = False,  # true in production
        app_env: Environment | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the pipeline stack.

        Args:
            scope: CDK construct scope
            construct_id: Construct ID
            github_owner: GitHub repository owner
            github_repo: GitHub repository name
            connection_arn: CodeStar connection ARN
            env_name: Environment name
            branch: Git branch to deploy from
            manual_approval: Whether to require manual approval for deployment
            app_env: AWS environment configuration
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        # Configure source code integration
        source = pipelines.CodePipelineSource.connection(
            f"{github_owner}/{github_repo}",
            branch,
            connection_arn=connection_arn,
        )

        # Configure build and synthesis step
        synth = pipelines.ShellStep(
            "Synth",
            input=source,
            commands=[
                "pip install -r requirements.txt",
                "npm i -g aws-cdk",
                f"cdk synth -c odyssey.env={env_name}",
            ],
        )

        # Create the main pipeline
        pipeline = pipelines.CodePipeline(
            self,
            "Odyssey-Static-Site-Pipeline",
            pipeline_name="Odyssey-Static-Site-Pipeline",
            synth=synth,
        )

        # Create application stage
        stage = AppStage(self, env_name.capitalize(), env_name=env_name, app_env=app_env)

        # Add stage with optional manual approval
        if manual_approval:
            pipeline.add_stage(stage, pre=[pipelines.ManualApprovalStep("ApproveDeployment")])
        else:
            pipeline.add_stage(stage)

        # Build the pipeline
        pipeline.build_pipeline()

        # Apply pipeline-specific IAM policies
        apply_policies_to_role(
            pipeline.pipeline.role,
            "pipeline.json",
        )
