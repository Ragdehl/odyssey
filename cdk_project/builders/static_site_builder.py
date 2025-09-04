"""
Static website builder for Odyssey CDK project.

This module provides a builder for creating static website infrastructure
using S3 for hosting and S3 deployment for automatic content updates.
It includes proper bucket configuration, public access settings, and
environment-specific removal policies.
"""

from __future__ import annotations
from pathlib import Path
from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    RemovalPolicy,
    CfnOutput,
    Stack,
)
from constructs import Construct
import os

class StaticWebsite(Construct):
    """
    Static website builder using S3 for hosting.
    
    Creates an S3 bucket configured for static website hosting with
    automatic deployment from the source directory.
    """
    def __init__(
            self, 
            scope: Construct, 
            construct_id: str, 
            *, 
            env_name: str
        ) -> None:
        """
        Initialize the static website builder.
        
        Args:
            scope: CDK construct scope
            construct_id: Construct ID
            env_name: Environment name for bucket naming and removal policy
        """
        super().__init__(scope, construct_id)
    
        account = Stack.of(self).account
        region  = Stack.of(self).region
        bucket_name = f"odyssey-chat-interface-{env_name.lower()}-{account}-{region}"

        # Create S3 bucket for static website hosting
        self.bucket = s3.Bucket(
            self,
            "SiteBucket",
            bucket_name=bucket_name,
            website_index_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_policy=False,
                block_public_acls=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            ),
            removal_policy=RemovalPolicy.RETAIN if env_name.lower() == "main" else RemovalPolicy.DESTROY,
            auto_delete_objects=(env_name.lower() != "main"),
        )

        # Get source directory path
        asset_dir = Path(__file__).resolve().parents[2] / "src"

        # Deploy website content to S3 bucket
        s3_deployment.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3_deployment.Source.asset(str(asset_dir))],
            destination_bucket=self.bucket,
        )

        # Output website URL for easy access
        CfnOutput(
            self,
            "WebsiteURL",
            value=self.bucket.bucket_website_url,
        )