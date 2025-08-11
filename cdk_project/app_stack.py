from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
import os

class StaticSiteStack(Stack):
    """
    Defines the infrastructure for a static website hosted on S3.
    This stack is environment-aware and will create resources
    with names and configurations based on the provided env_name.
    """
    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a unique bucket name based on the environment
        bucket_name = f"odyssey-chat-interface-{env_name.lower()}-{self.account}"

        # Define the S3 bucket for the static site
        site_bucket = s3.Bucket(
            self, f"SiteBucket-{env_name}",
            bucket_name=bucket_name,
            website_index_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_policy=False,
                block_public_acls=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            ),
            # In production, you want to retain your data. In dev, destroy it on stack deletion.
            removal_policy=RemovalPolicy.RETAIN if env_name.lower() == "main" else RemovalPolicy.DESTROY,
            auto_delete_objects=True if env_name.lower() != "main" else False
        )

        # Deploy the local index.html file to the S3 bucket
        s3_deployment.BucketDeployment(
            self, f"DeployWebsite-{env_name}",
            sources=[s3_deployment.Source.asset(os.path.join(os.path.dirname(__file__), "..", "src"))],
            destination_bucket=site_bucket
        )

        # Output the website URL for easy access
        CfnOutput(
            self, f"WebsiteURL-{env_name}",
            value=site_bucket.bucket_website_url,
            description=f"URL for the {env_name} static website"
        )